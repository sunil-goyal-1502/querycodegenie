from flask import Flask, request, jsonify, Response, make_response, send_from_directory, stream_with_context
from flask_cors import CORS
import json
import os
import tempfile
import logging
import threading
import time
from typing import Dict, List, Optional, Union, Any, Generator
from threading import Thread
import shutil

from .codeindexer import CodeIndexer
from .llm_client import OllamaClient
from .search_engine import SearchEngine
from .database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS with proper settings
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173", "http://127.0.0.1:5173"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "expose_headers": ["Content-Type"],
        "max_age": 600
    }
})

# Initialize global objects
indexer = CodeIndexer()
llm_client = OllamaClient()
search_engine = SearchEngine(llm_client=llm_client)
db = Database()

# Track the current indexing job
indexing_status = {
    "is_complete": False,
    "total_files": 0,
    "processed_files": 0,
    "failed_files": 0,
    "current_phase": "",
    "progress_percentage": 0,
    "file_types": {},
    "success_rate": 0,
    "is_loading": False,
    "current_batch": 0,
    "total_batches": 0,
    "current_file": "",
    "current_file_type": "",
    "methods_found": 0,
    "current_file_summary": "",
    "current_file_detailed_summary": "",
    "current_file_methods": [],
    "last_processed_file": "",
    "last_processed_file_type": "",
    "last_processed_file_summary": "",
    "last_processed_file_methods": []
}

def initialize_search_engine():
    """Initialize the search engine with the current codebase."""
    global search_engine
    if hasattr(indexer, 'file_contents') and indexer.file_contents:
        logger.info("Initializing search engine with codebase content")
        search_engine.build_graph(indexer.file_contents)
        logger.info("Search engine initialized successfully")
    else:
        logger.warning("No codebase content available for search engine initialization")

@app.route('/api/test-ollama', methods=['POST', 'OPTIONS'])
def test_ollama():
    """Test connection to Ollama server."""
    if request.method == 'OPTIONS':
        return make_response()
        
    try:
        data = request.get_json()
        base_url = data.get('base_url', 'http://localhost:11434')
        model = data.get('model', 'llama3:8b')
        
        # Update the LLM client with the new base URL and model
        llm_client.base_url = base_url
        llm_client.model = model
        
        # Test the connection
        is_connected = llm_client.test_connection()
        
        if is_connected:
            return jsonify({
                "connected": True,
                "message": "Successfully connected to Ollama server",
                "available_models": llm_client.get_available_models(),
                "suggested_model": llm_client.model
            })
        else:
            return jsonify({
                "connected": False,
                "message": "Failed to connect to Ollama server. Is it running?",
                "error": "Connection failed"
            }), 500
            
    except Exception as e:
        logger.error(f"Error testing Ollama connection: {str(e)}")
        return jsonify({
            "connected": False,
            "message": f"Error testing Ollama connection: {str(e)}",
            "error": str(e)
        }), 500

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
    """Load a repository for indexing."""
    try:
        data = request.json
        repo_url = data.get('repo_url')
        
        if not repo_url:
            return jsonify({"success": False, "error": "No repository URL provided"})
        
        # Create a temporary directory for the repository
        repo_path = os.path.join(tempfile.gettempdir(), 'querycodegenie_repo')
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        os.makedirs(repo_path)
        
        # Update indexing status to show loading
        db.update_indexing_status(
            total_files=0,
            processed_files=0,
            failed_files=0,
            success_rate=0,
            file_types={},
            languages={},
            is_complete=False,
            is_loading=True,
            repo_url=repo_url
        )
        
        # Start indexing in a background thread
        def index_repo():
            try:
                success = indexer.load_repository(repo_url, repo_path)
                if success:
                    db.update_indexing_status(
                        total_files=len(indexer.file_contents),
                        processed_files=len(indexer.file_contents),
                        failed_files=0,
                        success_rate=100.0,
                        file_types=indexer.get_codebase_summary().get("file_types", {}),
                        languages=indexer.get_codebase_summary().get("languages", {}),
                        is_complete=True,
                        is_loading=False,
                        repo_url=repo_url
                    )
                else:
                    db.update_indexing_status(
                        total_files=0,
                        processed_files=0,
                        failed_files=1,
                        success_rate=0.0,
                        file_types={},
                        languages={},
                        is_complete=True,
                        is_loading=False,
                        repo_url=repo_url
                    )
            except Exception as e:
                logger.error(f"Error indexing repository: {str(e)}")
                db.update_indexing_status(
                    total_files=0,
                    processed_files=0,
                    failed_files=1,
                    success_rate=0.0,
                    file_types={},
                    languages={},
                    is_complete=True,
                    is_loading=False,
                    repo_url=repo_url
                )
        
        thread = Thread(target=index_repo)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": "Repository indexing started",
            "status": db.get_indexing_status(repo_url)
        })
        
    except Exception as e:
        logger.error(f"Error loading repository: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/load-directory', methods=['POST'])
def load_directory():
    """Load a local directory for indexing."""
    data = request.json
    directory_path = data.get('directory_path')
    
    if not directory_path:
        return jsonify({"success": False, "error": "No directory path provided"})
    
    if not os.path.exists(directory_path):
        return jsonify({"success": False, "error": f"Directory does not exist: {directory_path}"})
    
    # Check if directory is already indexed
    status = db.get_indexing_status(directory_path)
    if status and status.get("success_rate", 0) > 95:
        indexing_status.update({
            "is_complete": True,
            "total_files": status["total_files"],
            "processed_files": status["processed_files"],
            "failed_files": status["failed_files"],
            "current_phase": "Using cached index",
            "progress_percentage": 100,
            "file_types": status["file_types"],
            "success_rate": status["success_rate"],
            "is_loading": False
        })
        return jsonify({"success": True, "message": "Using cached index"})
    
    # Reset indexer with new path
    global indexer
    indexer = CodeIndexer()
    
    # Start indexing in a background thread
    def index_directory_task():
        global indexing_status
        
        indexing_status.update({
            "is_complete": False,
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "current_phase": "Setting up directory",
            "progress_percentage": 10,
            "is_loading": True
        })
        
        # Load the directory
        success, message = indexer.load_directory(directory_path)
        
        if not success:
            indexing_status.update({
                "is_complete": False,
                "current_phase": f"Failed to load directory: {message}",
                "progress_percentage": 0,
                "is_loading": False
            })
            return
        
        indexing_status.update({
            "current_phase": "Directory loaded. Starting indexing...",
            "progress_percentage": 30
        })
        
        # Index the files
        result = indexer.index_files(directory_path)
        
        if result["status"] == "success":
            indexing_status.update({
                "is_complete": True,
                "total_files": result["stats"]["total_files"],
                "processed_files": result["stats"]["processed_files"],
                "failed_files": result["stats"]["failed_files"],
                "current_phase": "Complete",
                "progress_percentage": 100,
                "file_types": result["stats"]["file_types"],
                "success_rate": result["stats"]["success_rate"],
                "is_loading": False
            })
            # Initialize search engine after successful indexing
            initialize_search_engine()
        else:
            indexing_status.update({
                "is_complete": False,
                "current_phase": f"Indexing failed: {result['message']}",
                "progress_percentage": 0,
                "is_loading": False
            })
    
    thread = threading.Thread(target=index_directory_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Directory loading started"})

@app.route('/api/indexing-status', methods=['GET'])
def get_indexing_status():
    """Get detailed indexing status."""
    # Get the latest status from the database
    status = db.get_indexing_status(indexer.base_dir)
    if status:
        indexing_status.update(status)
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

def error_stream(message: str) -> Generator[str, None, None]:
    """Stream an error message."""
    yield json.dumps({"error": message, "done": True}) + "\n"

@app.route('/api/query', methods=['GET', 'POST'])
def query_code():
    """Handle code query requests."""
    try:
        # Get query from request
        query = request.args.get('query') if request.method == 'GET' else request.json.get('query')
        stream = request.args.get('stream', 'false').lower() == 'true' if request.method == 'GET' else request.json.get('stream', False)
        
        if not query:
            logger.error("No query provided")
            if stream:
                return Response(error_stream("No query provided"), mimetype='text/event-stream')
            return jsonify({"error": "No query provided"}), 400

        if not hasattr(indexer, 'file_contents') or not indexer.file_contents:
            logger.error("Codebase not indexed yet")
            if stream:
                return Response(error_stream("Codebase not indexed yet"), mimetype='text/event-stream')
            return jsonify({"error": "Codebase not indexed yet"}), 400

        if stream:
            def generate():
                try:
                    logger.info("Starting streaming response")
                    # Get relevant files and content for the query
                    relevant_files, relevant_content = search_engine.find_relevant_files(query)
                    
                    # Send relevant files first with their summaries
                    file_info = {
                        file_path: {
                            "summary": content.get("summary", "No summary available"),
                            "type": content.get("type", "unknown"),
                            "is_entry_point": content.get("is_entry_point", False),
                            "is_core_file": content.get("is_core_file", False),
                            "methods": [
                                {
                                    "name": m.get("name", ""),
                                    "type": m.get("type", ""),
                                    "summary": m.get("summary", "")
                                } for m in content.get("methods", [])
                            ]
                        } for file_path, content in relevant_content.items()
                    }
                    yield f"data: {json.dumps({'relevant_files': file_info})}\n\n"
                    
                    # Prepare context for LLM
                    context = {
                        "files": [
                            {
                                "path": file_path,
                                "content": content.get("content", ""),
                                "language": indexer.file_language.get(file_path, "unknown")
                            }
                            for file_path, content in relevant_content.items()
                        ],
                        "dependencies": {
                            file_path: content.get("relationships", {})
                            for file_path, content in relevant_content.items()
                        }
                    }
                    
                    # Stream LLM response
                    for chunk in llm_client.query_code(query, context):
                        if chunk:
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error in streaming response: {str(e)}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
            
            return Response(generate(), content_type='text/event-stream')
        else:
            # Non-streaming response handling
            relevant_files, relevant_content = search_engine.find_relevant_files(query)
            
            # Prepare context for LLM
            context = {
                "files": [
                    {
                        "path": file_path,
                        "content": content.get("content", ""),
                        "language": indexer.file_language.get(file_path, "unknown")
                    }
                    for file_path, content in relevant_content.items()
                ],
                "dependencies": {
                    file_path: content.get("relationships", {})
                    for file_path, content in relevant_content.items()
                }
            }
            
            # Collect all chunks into a single response
            chunks = []
            for chunk in llm_client.query_code(query, context):
                if chunk:
                    chunks.append(chunk)
            
            return jsonify({
                "success": True,
                "response": "".join(chunks),
                "relevant_files": {
                    file_path: {
                        "summary": content.get("summary", "No summary available"),
                        "type": content.get("type", "unknown"),
                        "is_entry_point": content.get("is_entry_point", False),
                        "is_core_file": content.get("is_core_file", False),
                        "methods": [
                            {
                                "name": m.get("name", ""),
                                "type": m.get("type", ""),
                                "summary": m.get("summary", "")
                            } for m in content.get("methods", [])
                        ]
                    } for file_path, content in relevant_content.items()
                }
            })
            
    except Exception as e:
        logger.error(f"Error in query_code: {str(e)}")
        if stream:
            return Response(error_stream(str(e)), mimetype='text/event-stream')
        return jsonify({"error": str(e)}), 500

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
        # For non-streaming responses, collect all chunks into a single response
        chunks = []
        try:
            for chunk in llm_client.suggest_code_changes(query, relevant_file_contents, relevant_dependencies):
                chunks.append(chunk)
            return jsonify({
                "success": True,
                "response": "".join(chunks),
                "relevant_files": list(relevant_file_contents.keys())
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "relevant_files": list(relevant_file_contents.keys())
            })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
