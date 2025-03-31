from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import os
import tempfile
import logging
import threading
import time
from typing import Dict, List, Optional, Union, Any, Generator

from codeindexer import CodeIndexer
from llm_client import OllamaClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Configure CORS to allow requests from any origin
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize global objects
indexer = CodeIndexer()
llm_client = OllamaClient()

# Track the current indexing job
indexing_status = {
    "is_indexing": False,
    "progress": 0,
    "message": "",
    "stats": {},
    "error": None
}

@app.route('/api/test-ollama', methods=['POST'])
def test_ollama_connection():
    """Test connection to the Ollama server."""
    data = request.json
    base_url = data.get('base_url', 'http://localhost:11434')
    model = data.get('model', 'deepseek-coder')
    
    global llm_client
    llm_client = OllamaClient(base_url=base_url, model=model)
    
    result = llm_client.test_connection()
    return jsonify(result)

@app.route('/api/set-model', methods=['POST'])
def set_model():
    """Change the model used by the LLM client."""
    data = request.json
    model_name = data.get('model')
    
    if not model_name:
        return jsonify({"success": False, "error": "No model name provided"})
    
    llm_client.set_model(model_name)
    return jsonify({"success": True, "message": f"Model changed to {model_name}"})

@app.route('/api/load-repo', methods=['POST'])
def load_repository():
    """Clone a repository for indexing."""
    data = request.json
    repo_url = data.get('repo_url')
    auth_token = data.get('auth_token')
    
    if not repo_url:
        return jsonify({"success": False, "error": "No repository URL provided"})
    
    # Reset indexer with new temp directory
    global indexer
    indexer = CodeIndexer(tempfile.mkdtemp())
    
    # Start indexing in a background thread
    def index_repo_task():
        global indexing_status
        
        indexing_status = {
            "is_indexing": True,
            "progress": 10,
            "message": "Cloning repository...",
            "stats": {},
            "error": None
        }
        
        # Clone the repository
        success, message = indexer.clone_repository(repo_url, auth_token)
        
        if not success:
            indexing_status = {
                "is_indexing": False,
                "progress": 0,
                "message": f"Failed to clone repository: {message}",
                "stats": {},
                "error": message
            }
            return
        
        indexing_status["progress"] = 30
        indexing_status["message"] = "Repository cloned. Starting indexing..."
        
        # Index the files
        success, message, stats = indexer.index_files()
        
        if success:
            indexing_status = {
                "is_indexing": False,
                "progress": 100,
                "message": "Indexing completed successfully",
                "stats": stats,
                "error": None
            }
        else:
            indexing_status = {
                "is_indexing": False,
                "progress": 0,
                "message": f"Indexing failed: {message}",
                "stats": {},
                "error": message
            }
    
    thread = threading.Thread(target=index_repo_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Repository loading started"})

@app.route('/api/load-directory', methods=['POST'])
def load_directory():
    """Load a local directory for indexing."""
    data = request.json
    directory_path = data.get('directory_path')
    
    if not directory_path:
        return jsonify({"success": False, "error": "No directory path provided"})
    
    if not os.path.exists(directory_path):
        return jsonify({"success": False, "error": f"Directory does not exist: {directory_path}"})
    
    # Reset indexer with new path
    global indexer
    indexer = CodeIndexer()
    
    # Start indexing in a background thread
    def index_directory_task():
        global indexing_status
        
        indexing_status = {
            "is_indexing": True,
            "progress": 10,
            "message": "Setting up directory...",
            "stats": {},
            "error": None
        }
        
        # Load the directory
        success, message = indexer.load_directory(directory_path)
        
        if not success:
            indexing_status = {
                "is_indexing": False,
                "progress": 0,
                "message": f"Failed to load directory: {message}",
                "stats": {},
                "error": message
            }
            return
        
        indexing_status["progress"] = 30
        indexing_status["message"] = "Directory loaded. Starting indexing..."
        
        # Index the files
        success, message, stats = indexer.index_files()
        
        if success:
            indexing_status = {
                "is_indexing": False,
                "progress": 100,
                "message": "Indexing completed successfully",
                "stats": stats,
                "error": None
            }
        else:
            indexing_status = {
                "is_indexing": False,
                "progress": 0,
                "message": f"Indexing failed: {message}",
                "stats": {},
                "error": message
            }
    
    thread = threading.Thread(target=index_directory_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Directory loading started"})

@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get the current status of the indexing process."""
    return jsonify(indexing_status)

@app.route('/api/file-structure', methods=['GET'])
def get_file_structure():
    """Get the file structure of the indexed codebase."""
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    structure = indexer.get_file_structure()
    return jsonify({"success": True, "structure": structure})

@app.route('/api/file-content', methods=['GET'])
def get_file_content():
    """Get the content of a specific file."""
    file_path = request.args.get('path')
    
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})
    
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    content = indexer.get_file_content(file_path)
    
    if content is None:
        return jsonify({"success": False, "error": f"File not found: {file_path}"})
    
    return jsonify({
        "success": True,
        "file_path": file_path,
        "content": content,
        "language": indexer.file_language.get(file_path, "unknown")
    })

@app.route('/api/search', methods=['GET'])
def search_codebase():
    """Search for a term in the codebase."""
    search_term = request.args.get('term')
    
    if not search_term:
        return jsonify({"success": False, "error": "No search term provided"})
    
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    results = indexer.search_codebase(search_term)
    return jsonify({"success": True, "results": results})

@app.route('/api/related-files', methods=['GET'])
def get_related_files():
    """Get files related to a specific file through imports and exports."""
    file_path = request.args.get('path')
    
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})
    
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    related = indexer.get_related_files(file_path)
    return jsonify({"success": True, "related": related})

@app.route('/api/codebase-summary', methods=['GET'])
def get_codebase_summary():
    """Get a summary of the indexed codebase."""
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    summary = indexer.get_codebase_summary()
    return jsonify({"success": True, "summary": summary})

@app.route('/api/analyze-codebase', methods=['POST'])
def analyze_codebase():
    """Analyze the codebase structure and provide high-level insights."""
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    # Get a subset of file contents and dependencies for the analysis
    file_contents = {path: content for path, content in list(indexer.file_contents.items())[:50]}
    dependencies = {path: list(deps) for path, deps in indexer.imports_map.items() if deps}
    
    result = llm_client.analyze_codebase(
        indexer.get_codebase_summary(),
        file_contents,
        dependencies
    )
    
    return jsonify(result)

@app.route('/api/query', methods=['POST'])
def query_code():
    """Answer a query about the codebase."""
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({"success": False, "error": "No query provided"})
    
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    # First, find relevant files
    file_list = list(indexer.file_contents.keys())
    file_summaries = {path: content[:500] + "..." for path, content in indexer.file_contents.items()}
    
    relevant_files_response = llm_client.find_relevant_files(query, file_list, file_summaries)
    
    if not relevant_files_response.get("success", False):
        return jsonify(relevant_files_response)
    
    # Parse the response to extract file paths
    # This is a simple extraction method and might need refinement
    response_text = relevant_files_response.get("response", "")
    mentioned_files = []
    
    for file_path in indexer.file_contents.keys():
        if file_path in response_text:
            mentioned_files.append(file_path)
    
    # Limit to top 10 most relevant files
    relevant_files = mentioned_files[:10] if mentioned_files else list(indexer.file_contents.keys())[:5]
    
    # Get content of relevant files
    relevant_file_contents = {path: indexer.file_contents[path] for path in relevant_files if path in indexer.file_contents}
    
    # Get dependencies between these files
    relevant_dependencies = {}
    for file in relevant_files:
        imports = list(indexer.imports_map.get(file, []))
        imported_by = [f for f, deps in indexer.imports_map.items() if file in deps]
        relevant_dependencies[file] = {
            "imports": [imp for imp in imports if imp in relevant_files],
            "imported_by": [imp for imp in imported_by if imp in relevant_files]
        }
    
    # Now, answer the query using relevant files
    stream = data.get('stream', False)
    
    if stream:
        def generate():
            try:
                for chunk in llm_client.query_code(query, relevant_file_contents, relevant_dependencies):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        return Response(generate(), content_type='text/event-stream')
    else:
        result = llm_client.query_code(query, relevant_file_contents, relevant_dependencies)
        result["relevant_files"] = list(relevant_file_contents.keys())
        return jsonify(result)

@app.route('/api/suggest-changes', methods=['POST'])
def suggest_code_changes():
    """Suggest changes to implement new features or fix issues."""
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({"success": False, "error": "No query provided"})
    
    if not indexer.indexed:
        return jsonify({"success": False, "error": "Codebase not indexed yet"})
    
    # Process similar to query_code but use suggest_code_changes method
    file_list = list(indexer.file_contents.keys())
    file_summaries = {path: content[:500] + "..." for path, content in indexer.file_contents.items()}
    
    relevant_files_response = llm_client.find_relevant_files(query, file_list, file_summaries)
    
    if not relevant_files_response.get("success", False):
        return jsonify(relevant_files_response)
    
    # Parse the response to extract file paths
    response_text = relevant_files_response.get("response", "")
    mentioned_files = []
    
    for file_path in indexer.file_contents.keys():
        if file_path in response_text:
            mentioned_files.append(file_path)
    
    # Limit to top 10 most relevant files
    relevant_files = mentioned_files[:10] if mentioned_files else list(indexer.file_contents.keys())[:5]
    
    # Get content of relevant files
    relevant_file_contents = {path: indexer.file_contents[path] for path in relevant_files if path in indexer.file_contents}
    
    # Get dependencies between these files
    relevant_dependencies = {}
    for file in relevant_files:
        imports = list(indexer.imports_map.get(file, []))
        imported_by = [f for f, deps in indexer.imports_map.items() if file in deps]
        relevant_dependencies[file] = {
            "imports": [imp for imp in imports if imp in relevant_files],
            "imported_by": [imp for imp in imported_by if imp in relevant_files]
        }
    
    # Now, suggest changes using relevant files
    stream = data.get('stream', False)
    
    if stream:
        def generate():
            try:
                for chunk in llm_client.suggest_code_changes(query, relevant_file_contents, relevant_dependencies):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        return Response(generate(), content_type='text/event-stream')
    else:
        result = llm_client.suggest_code_changes(query, relevant_file_contents, relevant_dependencies)
        result["relevant_files"] = list(relevant_file_contents.keys())
        return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
