import os
import re
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
import logging
from .database import Database
from .vector_db import VectorDB
import concurrent.futures
import time
from .llm_client import OllamaClient
from tree_sitter import Language, Parser
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CodeIndexer:
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or tempfile.mkdtemp()
        self.file_contents: Dict[str, str] = {}
        self.file_language: Dict[str, str] = {}
        self.file_summaries: Dict[str, str] = {}
        self.file_methods: Dict[str, List[Dict[str, Any]]] = {}
        self.imports_map: Dict[str, Set[str]] = {}
        self.exports_map: Dict[str, Set[str]] = {}
        self.references_map: Dict[str, Set[str]] = {}
        self.indexed = False
        self.llm_client = OllamaClient(model="llama3:8b")
        self.parser = Parser()
        self.vector_db = VectorDB()
        self.db = Database()
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize tree-sitter languages
        self.languages = {}
        self._init_tree_sitter_languages()
        
        # File extension to language mapping
        self.file_extension_to_language = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.rs': 'rust',
            '.r': 'r',
            '.m': 'matlab',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.less': 'less',
            '.vue': 'vue',
            '.svelte': 'svelte',
            '.clj': 'clojure',
            '.fs': 'fsharp',
            '.pl': 'perl',
            '.lua': 'lua',
        }
        
        # Binary file extensions to skip
        self.binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.svg',
            '.mp3', '.mp4', '.wav', '.avi', '.mov', '.webm',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.tar', '.gz', '.rar', '.7z',
            '.exe', '.dll', '.so', '.dylib', '.class', '.pyc', '.pyd',
            '.ttf', '.otf', '.woff', '.woff2', '.eot',
            '.db', '.sqlite', '.sqlite3',
        }
        
        # Files and directories to ignore
        self.ignore_patterns = [
            r'node_modules',
            r'\.git',
            r'\.github',
            r'\.vscode',
            r'\.idea',
            r'\.vs',
            r'__pycache__',
            r'venv',
            r'env',
            r'\.env',
            r'build',
            r'dist',
            r'\.cache',
            r'\.DS_Store',
            r'coverage',
        ]
        
        self.batch_size = 10
        self.max_workers = 4

    def _init_tree_sitter_languages(self):
        """Initialize tree-sitter languages for supported file types."""
        try:
            # Create a directory for language grammars if it doesn't exist
            grammar_dir = os.path.join(os.path.dirname(__file__), 'grammars')
            os.makedirs(grammar_dir, exist_ok=True)
            
            # Download and build language grammars
            languages = {
                'python': 'https://github.com/tree-sitter/tree-sitter-python',
                'javascript': 'https://github.com/tree-sitter/tree-sitter-javascript',
                'typescript': 'https://github.com/tree-sitter/tree-sitter-typescript',
                'java': 'https://github.com/tree-sitter/tree-sitter-java',
                'cpp': 'https://github.com/tree-sitter/tree-sitter-cpp',
                'go': 'https://github.com/tree-sitter/tree-sitter-go',
                'rust': 'https://github.com/tree-sitter/tree-sitter-rust',
                'ruby': 'https://github.com/tree-sitter/tree-sitter-ruby',
                'php': 'https://github.com/tree-sitter/tree-sitter-php',
            }
            
            for lang, repo in languages.items():
                try:
                    lang_dir = os.path.join(grammar_dir, f'tree-sitter-{lang}')
                    if not os.path.exists(lang_dir):
                        subprocess.run(['git', 'clone', repo, lang_dir], check=True)
                    
                    # Build the language
                    Language.build_library(
                        os.path.join(grammar_dir, f'{lang}.so'),
                        [lang_dir]
                    )
                    
                    # Load the language
                    self.languages[lang] = Language(os.path.join(grammar_dir, f'{lang}.so'), lang)
                    logger.info(f"Successfully initialized tree-sitter for {lang}")
                except Exception as e:
                    logger.error(f"Failed to initialize tree-sitter for {lang}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to initialize tree-sitter languages: {str(e)}")
    
    def should_ignore(self, path: str) -> bool:
        """Determine if a file or directory should be ignored during indexing."""
        for pattern in self.ignore_patterns:
            if re.search(pattern, path):
                return True
        return False
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if a file is binary based on its extension."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.binary_extensions
    
    def detect_language(self, file_path: str) -> str:
        """Detect programming language based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        return self.file_extension_to_language.get(ext, 'unknown')
    
    def clone_repository(self, repo_url: str, auth_token: Optional[str] = None) -> Tuple[bool, str]:
        """Clone a Git repository to the base directory."""
        try:
            # Create a clean temporary directory
            if os.path.exists(self.base_dir):
                shutil.rmtree(self.base_dir)
            os.makedirs(self.base_dir, exist_ok=True)
            
            # Prepare the clone command with authentication if provided
            if auth_token:
                # Insert token into URL for GitHub, GitLab, etc.
                if 'github.com' in repo_url:
                    repo_url = repo_url.replace('https://', f'https://{auth_token}@')
                elif 'gitlab.com' in repo_url:
                    repo_url = repo_url.replace('https://', f'https://oauth2:{auth_token}@')
            
            logger.info(f"Cloning repository: {repo_url} (with auth: {bool(auth_token)})")
            subprocess.run(['git', 'clone', repo_url, self.base_dir], 
                          check=True, 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE)
            
            return True, "Repository cloned successfully."
        except subprocess.CalledProcessError as e:
            error_msg = f"Git clone failed: {e.stderr.decode('utf-8')}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def load_directory(self, directory: str) -> Tuple[bool, str]:
        """Load code from a directory into the indexer."""
        try:
            # Set the base directory
            self.base_dir = directory
            if not os.path.exists(directory):
                return False, f"Directory does not exist: {directory}"
            
            logger.info(f"Loading directory: {directory}")
            return True, "Directory loaded successfully."
        except Exception as e:
            error_msg = f"Failed to load directory: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def index_files(self, repo_path: str) -> bool:
        """Index all files in the repository."""
        try:
            # Reset indexing status
            self.db.reset_indexing_status()
            
            # Get all files in the repository
            all_files = []
            for root, _, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
            
            total_files = len(all_files)
            processed_files = 0
            failed_files = 0
            indexed_files = []
            failed_files_details = []
            file_types = {}
            languages = {}
            
            # Update initial status
            self.db.update_indexing_status(
                total_files=total_files,
                processed_files=0,
                failed_files=0,
                success_rate=0.0,
                file_types={},
                languages={},
                indexed_files=[],
                failed_files_details=[],
                is_complete=False,
                is_loading=True,
                repo_url=repo_path
            )
            
            # Process each file
            for file_path in all_files:
                try:
                    # Process file
                    file_info = self._process_file(file_path)
                    
                    if file_info:
                        # Update file type and language counts
                        file_type = os.path.splitext(file_path)[1]
                        file_types[file_type] = file_types.get(file_type, 0) + 1
                        languages[file_info['language']] = languages.get(file_info['language'], 0) + 1
                        
                        # Save to database
                        self.db.save_file(
                            file_path=file_info['file_path'],
                            language=file_info['language'],
                            file_hash=file_info['file_hash'],
                            summary=file_info['summary'],
                            detailed_summary=file_info['detailed_summary'],
                            is_entry_point=file_info['is_entry_point'],
                            is_core_file=file_info['is_core_file']
                        )
                        
                        # Save methods
                        for method in file_info['methods']:
                            self.db.save_method(
                                file_path=file_info['file_path'],
                                method_name=method['name'],
                                method_type=method['type'],
                                line_numbers=method['line_numbers'],
                                summary=method['summary']
                            )
                        
                        indexed_files.append(file_path)
                    else:
                        failed_files += 1
                        failed_files_details.append({
                            'file_path': file_path,
                            'error': 'Processing failed'
                        })
                    
                    processed_files += 1
                    
                    # Update progress every 10 files or on last file
                    if processed_files % 10 == 0 or processed_files == total_files:
                        success_rate = (processed_files - failed_files) / processed_files if processed_files > 0 else 0.0
                        
                        self.db.update_indexing_status(
                            total_files=total_files,
                            processed_files=processed_files,
                            failed_files=failed_files,
                            success_rate=success_rate,
                            file_types=file_types,
                            languages=languages,
                            indexed_files=indexed_files,
                            failed_files_details=failed_files_details,
                            is_complete=(processed_files == total_files),
                            is_loading=(processed_files < total_files),
                            repo_url=repo_path
                        )
                        
                        self.logger.info(f"Processed {processed_files}/{total_files} files")
                
                except Exception as e:
                    self.logger.error(f"Error processing file {file_path}: {str(e)}")
                    failed_files += 1
                    failed_files_details.append({
                        'file_path': file_path,
                        'error': str(e)
                    })
                    processed_files += 1
            
            # Final status update
            success_rate = (processed_files - failed_files) / processed_files if processed_files > 0 else 0.0
            
            self.db.update_indexing_status(
                total_files=total_files,
                processed_files=processed_files,
                failed_files=failed_files,
                success_rate=success_rate,
                file_types=file_types,
                languages=languages,
                indexed_files=indexed_files,
                failed_files_details=failed_files_details,
                is_complete=True,
                is_loading=False,
                repo_url=repo_path
            )
            
            self.logger.info(f"Indexing completed. Processed {processed_files} files, {failed_files} failed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error indexing files: {str(e)}")
            return False

    def _parse_with_tree_sitter(self, content: str, language: str) -> Optional[Any]:
        """Parse code using tree-sitter."""
        try:
            # Get parser for language
            parser = self.languages.get(language)
            if not parser:
                self.logger.warning(f"No tree-sitter parser for language: {language}")
                return None
            
            # Create a new parser instance
            tree_sitter_parser = Parser()
            tree_sitter_parser.set_language(parser)
            
            # Parse content
            tree = tree_sitter_parser.parse(bytes(content, 'utf8'))
            return tree
            
        except Exception as e:
            self.logger.error(f"Error parsing with tree-sitter: {str(e)}")
            return None

    def _extract_methods_with_regex(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract methods using regex as a fallback."""
        try:
            methods = []
            
            # Define regex patterns based on language
            method_patterns = {
                'python': [
                    (r'^def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\):', 'function_definition'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*\(?([^)]*)\)?:', 'class_definition')
                ],
                'javascript': [
                    (r'^(?:function\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'typescript': [
                    (r'^(?:function\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'java': [
                    (r'^(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:[a-zA-Z0-9_<>]+\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'method_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'cpp': [
                    (r'^(?:[a-zA-Z0-9_<>]+\s+)?([a-zA-Z0-9_]+)\s*::\s*([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'method_definition'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_definition')
                ],
                'csharp': [
                    (r'^(?:public|private|protected)?\s*(?:static)?\s*(?:[a-zA-Z0-9_<>]+\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'method_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'go': [
                    (r'^func\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^type\s+([a-zA-Z0-9_]+)\s+struct\s*{', 'type_declaration')
                ],
                'ruby': [
                    (r'^def\s+([a-zA-Z0-9_]+)\s*\(?([^)]*)\)?', 'method'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class')
                ],
                'php': [
                    (r'^(?:public|private|protected)?\s*(?:static)?\s*function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'method_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'swift': [
                    (r'^func\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'kotlin': [
                    (r'^fun\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'scala': [
                    (r'^def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration'),
                    (r'^class\s+([a-zA-Z0-9_]+)\s*{', 'class_declaration')
                ],
                'rust': [
                    (r'^fn\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_item'),
                    (r'^struct\s+([a-zA-Z0-9_]+)\s*{', 'struct_item')
                ],
                'r': [
                    (r'^([a-zA-Z0-9_]+)\s*<-\s*function\s*\(([^)]*)\)\s*{', 'function_definition')
                ],
                'matlab': [
                    (r'^function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', 'function_definition')
                ],
                'shell': [
                    (r'^([a-zA-Z0-9_]+)\s*\(\s*\)\s*{', 'function_definition')
                ],
                'sql': [
                    (r'^CREATE\s+(?:OR\s+REPLACE)?\s+FUNCTION\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', 'function_definition')
                ],
                'vue': [
                    (r'^methods:\s*{', 'methods'),
                    (r'^([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'method_definition')
                ],
                'svelte': [
                    (r'^export\s+function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*{', 'function_declaration')
                ],
                'clojure': [
                    (r'^\(defn\s+([a-zA-Z0-9_]+)\s*\[([^\]]*)\]', 'function_definition')
                ],
                'fsharp': [
                    (r'^let\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*=', 'function_definition')
                ],
                'perl': [
                    (r'^sub\s+([a-zA-Z0-9_]+)\s*{', 'subroutine')
                ],
                'lua': [
                    (r'^function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', 'function_definition')
                ]
            }
            
            # Get patterns for language
            patterns = method_patterns.get(language, [])
            
            # Process each line
            lines = content.split('\n')
            for i, line in enumerate(lines):
                for pattern, method_type in patterns:
                    match = re.search(pattern, line)
                    if match:
                        method_name = match.group(1)
                        params = match.group(2) if len(match.groups()) > 1 else ''
                        
                        # Find method body
                        body_start = i
                        body_end = i
                        brace_count = 0
                        
                        # Count opening braces
                        for j in range(i, len(lines)):
                            line = lines[j]
                            brace_count += line.count('{')
                            brace_count -= line.count('}')
                            
                            if brace_count == 0:
                                body_end = j
                                break
                        
                        # Extract method body
                        method_body = '\n'.join(lines[body_start:body_end + 1])
                        
                        # Generate method summary using LLM
                        method_prompt = f"Please provide a concise summary of this {language} method:\n\n{method_body}"
                        method_summary = self.llm_client.generate(method_prompt)
                        
                        # Get line numbers
                        line_numbers = {
                            'start': body_start + 1,
                            'end': body_end + 1
                        }
                        
                        methods.append({
                            'name': method_name,
                            'type': method_type,
                            'body': method_body,
                            'parameters': params.split(','),
                            'summary': method_summary,
                            'line_numbers': line_numbers
                        })
            
            return methods
            
        except Exception as e:
            self.logger.error(f"Error extracting methods with regex: {str(e)}")
            return []

    def _extract_imports_with_regex(self, content: str, language: str) -> List[str]:
        """Extract imports using regex as a fallback."""
        try:
            imports = []
            
            # Define regex patterns based on language
            import_patterns = {
                'python': [
                    r'^import\s+([a-zA-Z0-9_.]+)',
                    r'^from\s+([a-zA-Z0-9_.]+)\s+import'
                ],
                'javascript': [
                    r'^import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
                    r'^require\s*\(\s*[\'"]([^\'"]+)[\'"]'
                ],
                'typescript': [
                    r'^import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
                    r'^require\s*\(\s*[\'"]([^\'"]+)[\'"]'
                ],
                'java': [
                    r'^import\s+([a-zA-Z0-9_.*]+);'
                ],
                'cpp': [
                    r'^#include\s+[<"]([^>"]+)[>"]'
                ],
                'csharp': [
                    r'^using\s+([a-zA-Z0-9_.]+);'
                ],
                'go': [
                    r'^import\s+[\'"]([^\'"]+)[\'"]'
                ],
                'ruby': [
                    r'^require\s+[\'"]([^\'"]+)[\'"]',
                    r'^require_relative\s+[\'"]([^\'"]+)[\'"]'
                ],
                'php': [
                    r'^use\s+([a-zA-Z0-9_\\]+);'
                ],
                'swift': [
                    r'^import\s+([a-zA-Z0-9_.]+)'
                ],
                'kotlin': [
                    r'^import\s+([a-zA-Z0-9_.]+)'
                ],
                'scala': [
                    r'^import\s+([a-zA-Z0-9_.]+)'
                ],
                'rust': [
                    r'^use\s+([a-zA-Z0-9_::]+);'
                ],
                'r': [
                    r'^library\s*\(\s*[\'"]([^\'"]+)[\'"]',
                    r'^require\s*\(\s*[\'"]([^\'"]+)[\'"]'
                ],
                'matlab': [
                    r'^import\s+([a-zA-Z0-9_.*]+)'
                ],
                'shell': [
                    r'^source\s+[\'"]([^\'"]+)[\'"]'
                ],
                'sql': [
                    r'^import\s+[\'"]([^\'"]+)[\'"]'
                ],
                'vue': [
                    r'^import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
                ],
                'svelte': [
                    r'^import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
                ],
                'clojure': [
                    r'^\(require\s+[\'"]([^\'"]+)[\'"]',
                    r'^\(use\s+[\'"]([^\'"]+)[\'"]'
                ],
                'fsharp': [
                    r'^open\s+([a-zA-Z0-9_.]+)'
                ],
                'perl': [
                    r'^use\s+([a-zA-Z0-9_:]+)',
                    r'^require\s+[\'"]([^\'"]+)[\'"]'
                ],
                'lua': [
                    r'^require\s*\(\s*[\'"]([^\'"]+)[\'"]'
                ]
            }
            
            # Get patterns for language
            patterns = import_patterns.get(language, [])
            
            # Process each line
            for line in content.split('\n'):
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        import_path = match.group(1)
                        import_path = import_path.strip('"\'').strip()
                        imports.append(import_path)
            
            return imports
            
        except Exception as e:
            self.logger.error(f"Error extracting imports with regex: {str(e)}")
            return []

    def _generate_summary(self, content: str, language: str) -> str:
        """Generate a summary of a file using LLM."""
        try:
            # Create prompt
            prompt = f"""Please provide a concise summary of this {language} file:

{content}

Summary:"""
            
            # Generate summary
            response = self.llm_client.generate(prompt)
            # Convert generator to string if needed
            if hasattr(response, '__iter__') and not isinstance(response, str):
                response = ''.join(response)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return "Summary generation failed"
    
    def _generate_detailed_summary(self, content: str, language: str) -> str:
        """Generate a detailed summary of a file using LLM."""
        try:
            # Create prompt
            prompt = f"""Please provide a detailed summary of this {language} file. Include:
1. Main purpose and functionality
2. Key components and their roles
3. Important methods/functions and their purposes
4. Any notable patterns or design decisions
5. Dependencies and relationships with other files

File content:
{content}

Detailed summary:"""
            
            # Generate summary
            response = self.llm_client.generate(prompt)
            # Convert generator to string if needed
            if hasattr(response, '__iter__') and not isinstance(response, str):
                response = ''.join(response)
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating detailed summary: {str(e)}")
            return "Detailed summary generation failed"
    
    def _process_file(self, file_path: str) -> Dict[str, Any]:
        """Process a single file and extract its metadata."""
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                self.logger.warning(f"File not found: {file_path}")
                return None
                
            if not os.access(file_path, os.R_OK):
                self.logger.warning(f"File not readable: {file_path}")
                return None

            # Skip binary files
            if self._is_binary(file_path):
                self.logger.info(f"Skipping binary file: {file_path}")
                return None

            # Skip files that shouldn't be indexed
            if not self._should_index(file_path):
                self.logger.info(f"Skipping file based on patterns: {file_path}")
                return None

            # Detect language
            language = self.detect_language(file_path)
            if not language:
                self.logger.warning(f"Could not detect language for file: {file_path}")
                return None

            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                self.logger.warning(f"Could not decode file as UTF-8: {file_path}")
                return None
            except Exception as e:
                self.logger.warning(f"Error reading file {file_path}: {str(e)}")
                return None

            # Generate summaries
            try:
                summary = self._generate_summary(content, language)
                detailed_summary = self._generate_detailed_summary(content, language)
            except Exception as e:
                self.logger.warning(f"Error generating summaries for {file_path}: {str(e)}")
                summary = "Summary generation failed"
                detailed_summary = "Detailed summary generation failed"

            # Extract imports and methods
            try:
                imports = self._extract_imports(content, language)
                methods = self._extract_methods(content, language)
            except Exception as e:
                self.logger.warning(f"Error extracting imports/methods for {file_path}: {str(e)}")
                imports = []
                methods = []

            # Determine file type
            is_entry_point = self._is_entry_point(file_path)
            is_core_file = self._is_core_file(file_path)

            # Calculate file hash
            file_hash = self._calculate_file_hash(content)

            # Store summaries and methods
            self.file_summaries[file_path] = summary
            self.file_methods[file_path] = methods

            return {
                'file_path': file_path,
                'language': language,
                'file_hash': file_hash,
                'summary': summary,
                'detailed_summary': detailed_summary,
                'imports': imports,
                'methods': methods,
                'is_entry_point': is_entry_point,
                'is_core_file': is_core_file
            }

        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}")
            return None

    def _parse_file(self, content: str, language: str) -> Optional[Any]:
        """Parse file content using tree-sitter."""
        try:
            if language not in self.languages:
                logger.warning(f"Language {language} not supported by tree-sitter")
                return None
            
            self.parser.set_language(self.languages[language])
            tree = self.parser.parse(bytes(content, 'utf8'))
            return tree
        except Exception as e:
            logger.error(f"Error parsing file with tree-sitter: {str(e)}")
            return None

    def _extract_methods_with_tree_sitter(self, tree: Any, language: str) -> List[Dict[str, Any]]:
        """Extract methods using tree-sitter AST."""
        try:
            methods = []
            
            # Get the root node
            root_node = tree.root_node
            
            # Define method node types based on language
            method_types = {
                'python': ['function_definition', 'method_definition'],
                'javascript': ['function_declaration', 'method_definition', 'arrow_function'],
                'typescript': ['function_declaration', 'method_definition', 'arrow_function'],
                'java': ['method_declaration'],
                'cpp': ['function_definition', 'method_definition'],
                'csharp': ['method_declaration'],
                'go': ['method_declaration', 'function_declaration'],
                'ruby': ['method', 'singleton_method'],
                'php': ['method_declaration'],
                'swift': ['function_declaration', 'method_declaration'],
                'kotlin': ['function_declaration', 'method_declaration'],
                'scala': ['function_declaration', 'method_declaration'],
                'rust': ['function_item', 'impl_item'],
                'r': ['function_definition'],
                'matlab': ['function_definition'],
                'shell': ['function_definition'],
                'sql': ['function_definition'],
                'vue': ['method_definition'],
                'svelte': ['method_definition'],
                'clojure': ['function_definition'],
                'fsharp': ['function_definition'],
                'perl': ['function_definition'],
                'lua': ['function_definition']
            }
            
            # Get method nodes
            method_nodes = []
            for node_type in method_types.get(language, []):
                method_nodes.extend(root_node.children_by_field_name(node_type))
            
            # Process each method node
            for node in method_nodes:
                # Get method name
                name_node = node.child_by_field_name('name')
                if not name_node:
                    continue
                
                method_name = content[name_node.start_byte:name_node.end_byte]
                
                # Get method body
                body_node = node.child_by_field_name('body')
                if not body_node:
                    continue
                
                method_body = content[body_node.start_byte:body_node.end_byte]
                
                # Get method parameters
                params_node = node.child_by_field_name('parameters')
                params = []
                if params_node:
                    for param_node in params_node.children:
                        if param_node.type == 'parameter':
                            param_name = content[param_node.start_byte:param_node.end_byte]
                            params.append(param_name)
                
                # Generate method summary using LLM
                method_prompt = f"Please provide a concise summary of this {language} method:\n\n{method_body}"
                method_summary = self.llm_client.generate(method_prompt)
                
                # Get line numbers
                line_numbers = {
                    'start': node.start_point[0] + 1,
                    'end': node.end_point[0] + 1
                }
                
                methods.append({
                    'name': method_name,
                    'type': node.type,
                    'body': method_body,
                    'parameters': params,
                    'summary': method_summary,
                    'line_numbers': line_numbers
                })
            
            return methods
            
        except Exception as e:
            self.logger.error(f"Error extracting methods with tree-sitter: {str(e)}")
            return []

    def _extract_imports_with_tree_sitter(self, tree: Any, language: str) -> List[str]:
        """Extract imports using tree-sitter AST."""
        try:
            imports = []
            root_node = tree.root_node
            
            # Define import node types based on language
            import_types = {
                'python': ['import_statement', 'import_from_statement'],
                'javascript': ['import_statement', 'import_declaration'],
                'typescript': ['import_statement', 'import_declaration'],
                'java': ['import_declaration'],
                'cpp': ['preproc_include'],
                'csharp': ['using_directive'],
                'go': ['import_spec', 'import_declaration'],
                'ruby': ['require', 'require_relative'],
                'php': ['use_declaration'],
                'swift': ['import_declaration'],
                'kotlin': ['import_directive'],
                'scala': ['import_declaration'],
                'rust': ['use_declaration'],
                'r': ['library', 'require'],
                'matlab': ['import'],
                'shell': ['source'],
                'sql': ['import'],
                'vue': ['import_statement'],
                'svelte': ['import_statement'],
                'clojure': ['require', 'use'],
                'fsharp': ['open'],
                'perl': ['use', 'require'],
                'lua': ['require']
            }
            
            # Get import nodes
            import_nodes = []
            for node_type in import_types.get(language, []):
                import_nodes.extend(root_node.children_by_field_name(node_type))
            
            # Process each import node
            for node in import_nodes:
                # Get import path
                path_node = node.child_by_field_name('path')
                if not path_node:
                    continue
                
                import_path = content[path_node.start_byte:path_node.end_byte]
                
                # Clean up import path
                import_path = import_path.strip('"\'').strip()
                
                # Add to imports list
                imports.append(import_path)
            
            return imports
            
        except Exception as e:
            self.logger.error(f"Error extracting imports with tree-sitter: {str(e)}")
            return []

    def search_codebase(self, query: str) -> List[Dict[str, any]]:
        """Search the codebase using vector similarity."""
        try:
            # Search vector database
            results = self.vector_db.search(query)
            
            # Group results by file
            file_results = {}
            for result in results:
                file_path = result['file_path']
                if file_path not in file_results:
                    file_results[file_path] = {
                        'file_path': file_path,
                        'relevance_score': result['relevance_score'],
                        'methods': []
                    }
                
                if result['type'] == 'method':
                    file_results[file_path]['methods'].append({
                        'name': result['method_name'],
                        'type': result['method_type'],
                        'body': result['method_body'],
                        'summary': result['method_summary'],
                        'line_numbers': result['line_numbers'],
                        'relevance_score': result['relevance_score']
                    })
            
            # Sort files by relevance score
            sorted_files = sorted(
                file_results.values(),
                key=lambda x: x['relevance_score'],
                reverse=True
            )
            
            return sorted_files
            
        except Exception as e:
            logger.error(f"Error searching codebase: {str(e)}")
            return []

    def get_file_content(self, file_path: str) -> Optional[Dict[str, any]]:
        """Get file content and metadata from vector database."""
        return self.vector_db.get_file_content(file_path)

    def get_file_structure(self) -> Dict[str, Dict]:
        """Return the file structure of the indexed codebase as a tree."""
        if not self.indexed:
            return {"error": "Codebase not indexed yet"}
        
        root = {}
        
        for file_path in sorted(self.file_contents.keys()):
            parts = file_path.split('/')
            current = root
            
            # Build the tree structure
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Leaf node (file)
                    current[part] = {
                        "type": "file",
                        "language": self.file_language.get(file_path, "unknown"),
                        "path": file_path
                    }
                else:  # Directory
                    if part not in current:
                        current[part] = {"type": "directory", "children": {}}
                    current = current[part]["children"]
        
        return {"root": root}

    def get_codebase_summary(self) -> Dict[str, Union[int, Dict[str, int]]]:
        """Generate a summary of the indexed codebase."""
        if not self.indexed:
            return {"error": "Codebase not indexed yet"}
        
        languages = {}
        for file_path, language in self.file_language.items():
            languages[language] = languages.get(language, 0) + 1
        
        return {
            "total_files": len(self.file_contents),
            "languages": languages,
            "file_relationships": {
                "imports": sum(len(imports) for imports in self.imports_map.values()),
                "references": sum(len(refs) for refs in self.references_map.values()),
            }
        }

    def _should_index_file(self, file_path: str) -> bool:
        """Determine if a file should be indexed based on its type and path."""
        try:
            # Get absolute path if not already
            abs_path = os.path.abspath(file_path)
            
            # Skip binary files
            if self.is_binary_file(abs_path):
                logger.debug(f"Skipping binary file: {abs_path}")
                return False
            
            # Skip ignored files and directories
            if self.should_ignore(abs_path):
                logger.debug(f"Skipping ignored file: {abs_path}")
                return False
            
            # Get file extension
            ext = os.path.splitext(abs_path)[1].lower()
            
            # Skip files with no extension
            if not ext:
                logger.debug(f"Skipping file with no extension: {abs_path}")
                return False
            
            # Check if file type is supported
            if ext not in self.file_extension_to_language:
                logger.debug(f"Skipping unsupported file type: {abs_path}")
                return False
            
            # Check if file exists and is readable
            if not os.path.isfile(abs_path):
                logger.debug(f"File does not exist: {abs_path}")
                return False
            
            # Check if file is empty
            if os.path.getsize(abs_path) == 0:
                logger.debug(f"Skipping empty file: {abs_path}")
                return False
            
            # Check if file is readable
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    f.read(1)  # Try to read first character
                    f.seek(0)  # Reset file pointer
                return True
            except (UnicodeDecodeError, IOError) as e:
                logger.debug(f"File not readable: {abs_path} - {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking if file should be indexed: {str(e)}")
            return False

    def _get_file_type(self, file_path: str) -> str:
        """Get the file type based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        return self.file_extension_to_language.get(ext, 'unknown')

    def _is_entry_point(self, file_path: str) -> bool:
        """Determine if a file is an entry point."""
        try:
            # Get file type from extension
            file_type = self.detect_language(file_path)
            
            # Define entry point patterns for different languages
            entry_point_patterns = {
                'python': ['main.py', '__main__.py', 'app.py', 'manage.py', 'wsgi.py', 'asgi.py'],
                'javascript': ['index.js', 'app.js', 'main.js', 'server.js'],
                'typescript': ['index.ts', 'app.ts', 'main.ts', 'server.ts'],
                'java': ['Main.java', 'Application.java'],
                'cpp': ['main.cpp', 'app.cpp'],
                'csharp': ['Program.cs', 'Startup.cs'],
                'go': ['main.go'],
                'rust': ['main.rs', 'lib.rs'],
                'ruby': ['app.rb', 'config.ru'],
                'php': ['index.php', 'app.php'],
                'swift': ['main.swift', 'App.swift'],
                'kotlin': ['Main.kt', 'Application.kt'],
                'scala': ['Main.scala', 'App.scala'],
                'r': ['main.R', 'app.R'],
                'matlab': ['main.m', 'app.m'],
                'shell': ['main.sh', 'run.sh'],
                'sql': ['main.sql', 'init.sql'],
                'vue': ['main.js', 'app.js'],
                'svelte': ['main.js', 'app.js'],
                'clojure': ['main.clj', 'app.clj'],
                'fsharp': ['Program.fs', 'App.fs'],
                'perl': ['main.pl', 'app.pl'],
                'lua': ['main.lua', 'app.lua']
            }
            
            # Get filename
            filename = os.path.basename(file_path)
            
            # Check if file is an entry point for its type
            return filename in entry_point_patterns.get(file_type, [])
            
        except Exception as e:
            self.logger.error(f"Error checking if file is entry point: {str(e)}")
            return False
    
    def _is_core_file(self, file_path: str) -> bool:
        """Check if a file is a core file."""
        try:
            # Get file name and directory
            file_name = os.path.basename(file_path)
            dir_name = os.path.dirname(file_path)
            
            # Define core patterns
            core_patterns = {
                'python': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'javascript': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'typescript': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'java': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'cpp': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'csharp': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'go': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'ruby': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'php': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'swift': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'kotlin': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'scala': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'rust': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'r': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'matlab': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'shell': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'sql': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'vue': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'svelte': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'clojure': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'fsharp': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'perl': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings'],
                'lua': ['core', 'base', 'common', 'utils', 'helpers', 'config', 'settings']
            }
            
            # Check if file is in core directory
            for lang, patterns in core_patterns.items():
                for pattern in patterns:
                    if pattern in dir_name.lower() or pattern in file_name.lower():
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if file is core file: {str(e)}")
            return False

    def load_repository(self, repo_url: str, repo_path: str) -> bool:
        """
        Load and index a repository from a given path.
        
        Args:
            repo_url: URL of the repository
            repo_path: Local path to the repository
            
        Returns:
            bool: True if indexing was successful, False otherwise
        """
        try:
            self.logger.info(f"Loading repository from {repo_url} to {repo_path}")
            
            # Update database status to indicate loading has started
            self.db.update_indexing_status(
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
            
            # Clone the repository
            try:
                if os.path.exists(repo_path):
                    shutil.rmtree(repo_path)
                os.makedirs(repo_path, exist_ok=True)
                
                # Clone the repository
                subprocess.run(['git', 'clone', repo_url, repo_path], check=True, capture_output=True)
                self.logger.info(f"Successfully cloned repository to {repo_path}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to clone repository: {e.stderr.decode()}")
                self.db.update_indexing_status(
                    total_files=0,
                    processed_files=0,
                    failed_files=1,
                    success_rate=0,
                    file_types={},
                    languages={},
                    is_complete=True,
                    is_loading=False,
                    repo_url=repo_url
                )
                return False
            
            # Index all files in the repository
            result = self.index_files(repo_path)
            
            # Update status to indicate loading is complete
            if result["status"] == "success":
                self.db.update_indexing_status(
                    total_files=result["stats"]["total_files"],
                    processed_files=result["stats"]["processed_files"],
                    failed_files=result["stats"]["failed_files"],
                    success_rate=result["stats"]["success_rate"],
                    file_types=result["stats"]["file_types"],
                    languages=result["stats"]["languages"],
                    is_complete=True,
                    is_loading=False,
                    repo_url=repo_url
                )
                self.logger.info(f"Repository loading completed with success={True}")
                return True
            else:
                self.db.update_indexing_status(
                    total_files=0,
                    processed_files=0,
                    failed_files=1,
                    success_rate=0,
                    file_types={},
                    languages={},
                    is_complete=True,
                    is_loading=False,
                    repo_url=repo_url
                )
                self.logger.error(f"Repository loading failed: {result['message']}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error loading repository: {str(e)}")
            # Update status to indicate loading failed
            self.db.update_indexing_status(
                total_files=0,
                processed_files=0,
                failed_files=0,
                success_rate=0,
                file_types={},
                languages={},
                is_complete=False,
                is_loading=False,
                repo_url=repo_url
            )
            return False

    def _should_index(self, file_path: str) -> bool:
        """Determine if a file should be indexed."""
        try:
            # Skip hidden files and directories
            if os.path.basename(file_path).startswith('.'):
                self.logger.debug(f"Skipping hidden file: {file_path}")
                return False
            
            # Skip binary files
            if self._is_binary(file_path):
                self.logger.debug(f"Skipping binary file: {file_path}")
                return False
            
            # Skip files in excluded directories
            excluded_dirs = {
                '.git', '.svn', '.hg', '__pycache__', 'node_modules',
                'venv', 'env', '.env', 'dist', 'build', 'target',
                'coverage', '.coverage', 'logs', 'log'
            }
            for dir_name in excluded_dirs:
                if dir_name in file_path.split(os.sep):
                    self.logger.debug(f"Skipping file in excluded directory: {file_path}")
                    return False
            
            # Skip files with excluded extensions
            excluded_extensions = {
                '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
                '.zip', '.tar', '.gz', '.rar', '.7z', '.pdf',
                '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg',
                '.mp3', '.mp4', '.avi', '.mov', '.wav', '.ogg',
                '.ttf', '.woff', '.woff2', '.eot', '.otf'
            }
            if os.path.splitext(file_path)[1].lower() in excluded_extensions:
                self.logger.debug(f"Skipping file with excluded extension: {file_path}")
                return False
            
            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                self.logger.warning(f"File is not readable: {file_path}")
                return False
            
            # Check if file exists
            if not os.path.exists(file_path):
                self.logger.warning(f"File does not exist: {file_path}")
                return False
            
            # Check if file is empty
            if os.path.getsize(file_path) == 0:
                self.logger.debug(f"Skipping empty file: {file_path}")
                return False
            
            # Check if file is too large (e.g., > 10MB)
            if os.path.getsize(file_path) > 10 * 1024 * 1024:
                self.logger.warning(f"File is too large: {file_path}")
                return False
            
            # Try to read the file to ensure it's not corrupted
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(1)
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {str(e)}")
                return False
            
            self.logger.debug(f"File will be indexed: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking if file should be indexed: {str(e)}")
            return False

    def _is_binary(self, file_path: str) -> bool:
        """Check if a file is binary."""
        try:
            # Check file size
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB
                return True
            
            # Check file content
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:
                    return True
                
                # Check for non-text characters
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
                return bool(chunk.translate(None, text_chars))
                
        except Exception as e:
            self.logger.error(f"Error checking if file is binary: {str(e)}")
            return True

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract imports using tree-sitter or regex as fallback."""
        try:
            # Try tree-sitter first
            if language in self.languages:
                tree = self._parse_with_tree_sitter(content, language)
                if tree:
                    imports = self._extract_imports_with_tree_sitter(tree, language)
                    if imports:
                        return imports
            
            # Fall back to regex
            return self._extract_imports_with_regex(content, language)
            
        except Exception as e:
            self.logger.error(f"Error extracting imports: {str(e)}")
            return []

    def _calculate_file_hash(self, content: str) -> str:
        """Calculate a hash of the file content."""
        try:
            # Create a hash object
            hash_obj = hashlib.sha256()
            
            # Update hash with content
            hash_obj.update(content.encode('utf-8'))
            
            # Return hexadecimal representation of hash
            return hash_obj.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error calculating file hash: {str(e)}")
            return "hash_calculation_failed"

    def _extract_methods(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract methods using tree-sitter or regex as fallback."""
        try:
            # Try tree-sitter first
            if language in self.languages:
                tree = self._parse_with_tree_sitter(content, language)
                if tree:
                    methods = self._extract_methods_with_tree_sitter(tree, language)
                    if methods:
                        return methods
            
            # Fall back to regex
            return self._extract_methods_with_regex(content, language)
            
        except Exception as e:
            self.logger.error(f"Error extracting methods: {str(e)}")
            return []
