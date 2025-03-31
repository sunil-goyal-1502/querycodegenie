
import os
import re
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CodeIndexer:
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or tempfile.mkdtemp()
        self.file_contents: Dict[str, str] = {}
        self.file_language: Dict[str, str] = {}
        self.imports_map: Dict[str, Set[str]] = {}
        self.exports_map: Dict[str, Set[str]] = {}
        self.references_map: Dict[str, Set[str]] = {}
        self.indexed = False
        self.file_extension_to_language = {
            # Web
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'scss',
            '.less': 'less',
            
            # Python
            '.py': 'python',
            '.ipynb': 'jupyter',
            
            # JVM Languages
            '.java': 'java',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.groovy': 'groovy',
            
            # C-family
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            
            # Ruby
            '.rb': 'ruby',
            '.erb': 'ruby',
            
            # PHP
            '.php': 'php',
            
            # Go
            '.go': 'go',
            
            # Rust
            '.rs': 'rust',
            
            # Swift
            '.swift': 'swift',
            
            # Markdown and docs
            '.md': 'markdown',
            '.markdown': 'markdown',
            '.rst': 'restructuredtext',
            
            # Config files
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.xml': 'xml',
            '.ini': 'ini',
            '.conf': 'config',
            
            # Shell
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'zsh',
            '.fish': 'fish',
            '.bat': 'batch',
            '.cmd': 'batch',
            '.ps1': 'powershell',
            
            # Misc
            '.sql': 'sql',
            '.graphql': 'graphql',
            '.r': 'r',
            '.dart': 'dart',
            '.hs': 'haskell',
            '.ex': 'elixir',
            '.exs': 'elixir',
            '.elm': 'elm',
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
    
    def index_files(self) -> Tuple[bool, str, Dict[str, int]]:
        """Index all files in the base directory."""
        try:
            self.file_contents = {}
            self.file_language = {}
            self.imports_map = {}
            self.exports_map = {}
            self.references_map = {}
            
            # Statistics to report progress
            stats = {
                "total_files": 0,
                "indexed_files": 0,
                "skipped_files": 0,
                "binary_files": 0,
                "by_language": {}
            }
            
            logger.info(f"Starting indexing of {self.base_dir}")
            
            # Walk through all files
            for root, dirs, files in os.walk(self.base_dir):
                # Filter out directories that should be ignored
                dirs[:] = [d for d in dirs if not self.should_ignore(os.path.join(root, d))]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    
                    stats["total_files"] += 1
                    
                    # Skip files that should be ignored
                    if self.should_ignore(file_path):
                        stats["skipped_files"] += 1
                        continue
                    
                    # Skip binary files
                    if self.is_binary_file(file_path):
                        stats["binary_files"] += 1
                        continue
                    
                    # Detect language
                    language = self.detect_language(file_path)
                    self.file_language[rel_path] = language
                    
                    # Update language stats
                    stats["by_language"][language] = stats["by_language"].get(language, 0) + 1
                    
                    # Read file content
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                            self.file_contents[rel_path] = content
                            stats["indexed_files"] += 1
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {str(e)}")
                        stats["skipped_files"] += 1
                        continue
            
            # After indexing all files, analyze dependencies
            self._analyze_dependencies()
            
            self.indexed = True
            logger.info(f"Indexing completed. Indexed {stats['indexed_files']} files.")
            
            return True, "Indexing completed successfully.", stats
        except Exception as e:
            error_msg = f"Failed to index files: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def _analyze_dependencies(self):
        """Analyze dependencies between files based on imports, exports, and references."""
        for file_path, content in self.file_contents.items():
            language = self.file_language.get(file_path, 'unknown')
            
            # Initialize empty sets for this file
            self.imports_map[file_path] = set()
            self.exports_map[file_path] = set()
            self.references_map[file_path] = set()
            
            # Based on language, extract import/export information
            if language in ['javascript', 'typescript']:
                self._analyze_js_ts_deps(file_path, content)
            elif language == 'python':
                self._analyze_python_deps(file_path, content)
            elif language in ['java', 'kotlin']:
                self._analyze_jvm_deps(file_path, content)
            # Add more language-specific analyzers as needed
    
    def _analyze_js_ts_deps(self, file_path: str, content: str):
        """Analyze dependencies in JavaScript/TypeScript files."""
        # Simple regex patterns for imports (not exhaustive)
        import_patterns = [
            r'import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'require\([\'"]([^\'"]+)[\'"]\)',
            r'import\([\'"]([^\'"]+)[\'"]\)',
        ]
        
        # Extract potential imports
        for pattern in import_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                import_path = match.group(1)
                
                # Handle relative imports
                if import_path.startswith('.'):
                    import_path = self._resolve_relative_import(file_path, import_path)
                
                if import_path:
                    self.imports_map[file_path].add(import_path)
                    
                    # Add reverse reference
                    if import_path in self.references_map:
                        self.references_map[import_path].add(file_path)
                    else:
                        self.references_map[import_path] = {file_path}
    
    def _analyze_python_deps(self, file_path: str, content: str):
        """Analyze dependencies in Python files."""
        # Simple regex patterns for imports (not exhaustive)
        import_patterns = [
            r'import\s+(\w+(?:\.\w+)*)',
            r'from\s+(\w+(?:\.\w+)*)\s+import',
        ]
        
        # Extract potential imports
        for pattern in import_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                import_path = match.group(1)
                import_parts = import_path.split('.')
                
                # Try to find the imported module in the codebase
                potential_file_path = self._find_python_module(import_parts)
                if potential_file_path:
                    self.imports_map[file_path].add(potential_file_path)
                    
                    # Add reverse reference
                    if potential_file_path in self.references_map:
                        self.references_map[potential_file_path].add(file_path)
                    else:
                        self.references_map[potential_file_path] = {file_path}
    
    def _analyze_jvm_deps(self, file_path: str, content: str):
        """Analyze dependencies in Java/Kotlin files."""
        # Simple regex patterns for imports (not exhaustive)
        import_patterns = [
            r'import\s+([a-zA-Z0-9_.]+)(?:\s*;\s*|\s+)',
        ]
        
        # Extract potential imports
        for pattern in import_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                import_path = match.group(1)
                
                # Try to find the imported class in the codebase
                potential_file_path = self._find_jvm_class(import_path)
                if potential_file_path:
                    self.imports_map[file_path].add(potential_file_path)
                    
                    # Add reverse reference
                    if potential_file_path in self.references_map:
                        self.references_map[potential_file_path].add(file_path)
                    else:
                        self.references_map[potential_file_path] = {file_path}
    
    def _resolve_relative_import(self, source_file: str, import_path: str) -> Optional[str]:
        """Resolve a relative import path to an absolute path in the codebase."""
        source_dir = os.path.dirname(source_file)
        
        # Handle ./ and ../ imports
        if import_path.startswith('./'):
            import_path = import_path[2:]
        elif import_path.startswith('../'):
            parts_to_remove = import_path.count('../')
            source_parts = source_dir.split('/')
            if len(source_parts) <= parts_to_remove:
                return None
            
            source_dir = '/'.join(source_parts[:-parts_to_remove])
            import_path = import_path.replace('../', '', parts_to_remove)
        
        # Try different extensions for the import
        potential_extensions = ['.js', '.jsx', '.ts', '.tsx', '']
        for ext in potential_extensions:
            full_path = os.path.normpath(os.path.join(source_dir, import_path + ext))
            if full_path in self.file_contents:
                return full_path
            
            # Check for index files in directories
            index_path = os.path.normpath(os.path.join(source_dir, import_path, 'index.js'))
            if index_path in self.file_contents:
                return index_path
            
            index_path = os.path.normpath(os.path.join(source_dir, import_path, 'index.ts'))
            if index_path in self.file_contents:
                return index_path
        
        return None
    
    def _find_python_module(self, import_parts: List[str]) -> Optional[str]:
        """Find a Python module in the codebase based on its import path."""
        # Try direct match (e.g., foo.bar.baz -> foo/bar/baz.py)
        path = '/'.join(import_parts) + '.py'
        if path in self.file_contents:
            return path
        
        # Try with __init__.py (e.g., foo.bar -> foo/bar/__init__.py)
        init_path = os.path.join('/'.join(import_parts), '__init__.py')
        if init_path in self.file_contents:
            return init_path
        
        return None
    
    def _find_jvm_class(self, import_path: str) -> Optional[str]:
        """Find a Java/Kotlin class in the codebase based on its import path."""
        # Convert package.path.Class to package/path/Class.java or .kt
        path_parts = import_path.split('.')
        
        # Try Java
        java_path = '/'.join(path_parts) + '.java'
        if java_path in self.file_contents:
            return java_path
        
        # Try Kotlin
        kotlin_path = '/'.join(path_parts) + '.kt'
        if kotlin_path in self.file_contents:
            return kotlin_path
        
        return None
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get the content of a specific file."""
        return self.file_contents.get(file_path)
    
    def search_codebase(self, search_term: str) -> Dict[str, List[Dict[str, Union[str, int]]]]:
        """Search for a term in the codebase and return matches with context."""
        results = {}
        
        for file_path, content in self.file_contents.items():
            matches = []
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if search_term.lower() in line.lower():
                    # Get some context (3 lines before and after)
                    start = max(0, i - 3)
                    end = min(len(lines) - 1, i + 3)
                    
                    context = "\n".join(lines[start:end+1])
                    matches.append({
                        "line_number": i + 1,
                        "line": line,
                        "context": context
                    })
            
            if matches:
                results[file_path] = matches
        
        return results
    
    def get_related_files(self, file_path: str) -> Dict[str, List[str]]:
        """Find files related to the given file through imports and references."""
        if not self.indexed:
            return {"error": "Codebase not indexed yet"}
        
        if file_path not in self.file_contents:
            return {"error": f"File not found: {file_path}"}
        
        imported_by = list(self.references_map.get(file_path, []))
        imports = list(self.imports_map.get(file_path, []))
        
        return {
            "file": file_path,
            "imports": imports,
            "imported_by": imported_by
        }
    
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
    
    def create_index_for_llm(self) -> Dict[str, Union[List[Dict[str, str]], Dict[str, List[str]]]]:
        """Create a structured index for the LLM to understand the codebase."""
        if not self.indexed:
            return {"error": "Codebase not indexed yet"}
        
        files_data = []
        for file_path, content in self.file_contents.items():
            language = self.file_language.get(file_path, "unknown")
            
            # Only include non-binary, known language files
            if language != "unknown":
                files_data.append({
                    "path": file_path,
                    "language": language,
                    "content": content
                })
        
        # Create dependency information
        dependencies = {}
        for file_path, imports in self.imports_map.items():
            if imports:
                dependencies[file_path] = list(imports)
        
        return {
            "files": files_data,
            "dependencies": dependencies,
            "summary": self.get_codebase_summary()
        }
