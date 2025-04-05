import os
import json
import logging
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CodeNode:
    def __init__(self, file_path: str, content: str, llm_client=None):
        try:
            self.file_path = file_path
            self.content = content
            self.file_type = self._get_file_type()
            self.methods = self._extract_methods()
            self.imports = set()
            self.imported_by = set()
            self.references = set()
            self.referenced_by = set()
            self.embedding = None
            self.method_embeddings = {}
            self.is_entry_point = self._is_entry_point()
            self.is_core_file = self._is_core_file()
            self.purpose = self._extract_purpose()
            self.keywords = self._extract_keywords()
            self.features = self._extract_features()
            self.llm_client = llm_client
            self.detailed_summary = None
            self.method_details = {}
            self.method_summaries = self._generate_method_summaries()
            
            # Generate detailed summaries if LLM client is available
            if self.llm_client:
                self._generate_detailed_summaries()
            
            # Generate the final summary after all other attributes are set
            self.summary = self._generate_summary()
            logger.info(f"CodeNode initialized successfully for {file_path}")
        except Exception as e:
            logger.error(f"Error initializing CodeNode for {file_path}: {str(e)}")
            raise
    
    def _get_file_type(self) -> str:
        ext = os.path.splitext(self.file_path)[1].lower()
        file_types = {
            'python': ['.py'],
            'typescript': ['.ts', '.tsx'],
            'javascript': ['.js', '.jsx'],
            'html': ['.html'],
            'css': ['.css'],
            'json': ['.json'],
            'markdown': ['.md']
        }
        for lang, extensions in file_types.items():
            if ext in extensions:
                return lang
        return 'unknown'
    
    def _extract_methods(self) -> List[Dict]:
        methods = []
        try:
            if self.file_type == 'python':
                patterns = [
                    (r'def\s+(\w+)\s*\((.*?)\):', 'function'),
                    (r'class\s+(\w+)\s*\((.*?)\):', 'class'),
                    (r'class\s+(\w+):', 'class')
                ]
            elif self.file_type in ['typescript', 'javascript']:
                patterns = [
                    (r'function\s+(\w+)\s*\((.*?)\)\s*{', 'function'),
                    (r'const\s+(\w+)\s*=\s*function\s*\((.*?)\)\s*{', 'function'),
                    (r'class\s+(\w+)\s*{', 'class'),
                    (r'(\w+)\s*:\s*function\s*\((.*?)\)\s*{', 'method'),
                    (r'(\w+)\s*:\s*\((.*?)\)\s*=>\s*{', 'method'),
                    (r'(\w+)\s*=\s*\((.*?)\)\s*=>\s*{', 'method'),
                    (r'(\w+)\s*=\s*async\s*\((.*?)\)\s*=>\s*{', 'method'),
                    (r'(\w+)\s*=\s*async\s*function\s*\((.*?)\)\s*{', 'method')
                ]
            else:
                return methods
            
            for pattern, method_type in patterns:
                matches = re.finditer(pattern, self.content)
                for match in matches:
                    try:
                        name = match.group(1)
                        start_pos = match.end()
                        next_match = re.search(pattern, self.content[start_pos:])
                        end_pos = start_pos + next_match.start() if next_match else len(self.content)
                        body = self.content[start_pos:end_pos].strip()
                        
                        # Get documentation
                        docstring = ""
                        if self.file_type == 'python':
                            doc_match = re.search(r'"""(.*?)"""', body, re.DOTALL)
                        else:
                            doc_match = re.search(r'/\*\*(.*?)\*/', body, re.DOTALL)
                        if doc_match:
                            docstring = doc_match.group(1).strip()
                        
                        methods.append({
                            'name': name,
                            'type': method_type,
                            'body': body,
                            'docstring': docstring,
                            'position': start_pos
                        })
                    except Exception as e:
                        logger.error(f"Error extracting method {name if 'name' in locals() else 'unknown'} in {self.file_path}: {str(e)}")
                        continue
            
            return methods
        except Exception as e:
            logger.error(f"Error in _extract_methods for {self.file_path}: {str(e)}")
            return methods
    
    def _is_entry_point(self) -> bool:
        """Check if this file is an entry point of the application."""
        entry_point_patterns = [
            r'if\s+__name__\s*==\s*[\'"]__main__[\'"]',
            r'main\s*\(\)',
            r'app\.run',
            r'index\.html',
            r'index\.js',
            r'index\.ts'
        ]
        return any(re.search(pattern, self.content) for pattern in entry_point_patterns)
    
    def _is_core_file(self) -> bool:
        """Check if this file contains core functionality."""
        core_patterns = [
            r'class\s+.*?Manager',
            r'class\s+.*?Service',
            r'class\s+.*?Handler',
            r'class\s+.*?Controller',
            r'class\s+.*?Processor',
            r'class\s+.*?Engine',
            r'class\s+.*?Client',
            r'class\s+.*?Server'
        ]
        return any(re.search(pattern, self.content) for pattern in core_patterns)
    
    def _extract_purpose(self) -> str:
        """Extract the purpose of this file from its content and documentation."""
        # Look for purpose in docstrings
        docstring_patterns = [
            r'"""(.*?)"""',  # Python docstrings
            r'/\*\*(.*?)\*/',  # JSDoc comments
            r'#\s*(.*?)$'  # Single-line comments
        ]
        
        purpose = []
        
        # Check file-level documentation
        for pattern in docstring_patterns:
            matches = re.finditer(pattern, self.content, re.MULTILINE)
            for match in matches:
                doc = match.group(1).strip()
                if len(doc) > 20:  # Only consider substantial documentation
                    purpose.append(doc)
        
        # Check method documentation for core functionality
        for method in self.methods:
            if method['docstring'] and len(method['docstring']) > 20:
                purpose.append(method['docstring'])
        
        # If no clear purpose found, analyze the code structure
        if not purpose:
            if self.is_entry_point:
                purpose.append("This is an entry point file that starts the application.")
            if self.is_core_file:
                purpose.append("This file contains core functionality for the application.")
        
        return "\n".join(purpose) if purpose else "Purpose not explicitly documented."
    
    def _generate_method_summaries(self) -> Dict[str, str]:
        """Generate summaries for each method in the file."""
        summaries = {}
        for method in self.methods:
            summary = []
            # Add method signature
            summary.append(f"{method['type'].title()} {method['name']}")
            
            # Add docstring if available
            if method['docstring']:
                summary.append(f"Purpose: {method['docstring']}")
            
            # Try to extract parameters and return type from the signature
            if method['type'] == 'function':
                params_match = re.search(r'\((.*?)\)', method['body'])
                if params_match:
                    params = params_match.group(1).strip()
                    if params:
                        summary.append(f"Parameters: {params}")
            
            # Look for return statements
            returns = re.findall(r'return\s+(.+?)(?:\n|$)', method['body'])
            if returns:
                summary.append("Returns: " + ", ".join(returns))
            
            summaries[method['name']] = "\n".join(summary)
        
        return summaries
    
    def _generate_detailed_summaries(self) -> None:
        """Generate detailed summaries using LLM."""
        if not self.llm_client:
            return
        
        try:
            # Generate detailed file summary
            file_prompt = f"""Please analyze this code file and provide a detailed explanation:

File: {self.file_path}
Type: {self.file_type}
Content:
{self.content}

Please provide:
1. A comprehensive overview of what this file does
2. The main purpose and functionality
3. Key components and their roles
4. Important dependencies and relationships
5. Any notable patterns or design decisions

Format your response in a clear, structured way."""

            response = self.llm_client.generate(file_prompt, temperature=0.3)
            if isinstance(response, dict) and "error" in response:
                logger.error(f"Error generating file summary for {self.file_path}: {response['error']}")
                self.detailed_summary = f"Error generating detailed summary: {response['error']}"
            else:
                # Handle both string and dict responses
                self.detailed_summary = response if isinstance(response, str) else response.get("response", "")
            
            # Generate detailed method summaries
            for method in self.methods:
                try:
                    method_prompt = f"""Please analyze this method and provide a detailed explanation:

File: {self.file_path}
Method: {method['name']}
Type: {method['type']}
Parameters: {method.get('parameters', '')}
Content:
{method['body']}

Please provide:
1. A detailed explanation of what this method does
2. Step-by-step breakdown of its functionality
3. Description of parameters and their purposes
4. Return values and their meanings
5. Any important side effects or dependencies

Format your response in a clear, structured way."""

                    response = self.llm_client.generate(method_prompt, temperature=0.3)
                    if isinstance(response, dict) and "error" in response:
                        logger.error(f"Error generating method summary for {method['name']} in {self.file_path}: {response['error']}")
                        self.method_details[method['name']] = f"Error generating detailed summary: {response['error']}"
                    else:
                        # Handle both string and dict responses
                        self.method_details[method['name']] = response if isinstance(response, str) else response.get("response", "")
                except Exception as e:
                    logger.error(f"Error generating detailed summary for method {method['name']} in {self.file_path}: {str(e)}")
                    self.method_details[method['name']] = f"Error generating detailed summary: {str(e)}"
            
            logger.info(f"Generated detailed summaries for {self.file_path}")
        except Exception as e:
            logger.error(f"Error generating detailed summaries for {self.file_path}: {str(e)}")
            self.detailed_summary = f"Error generating detailed summary: {str(e)}"
    
    def _generate_summary(self) -> str:
        """Generate a rich summary of the file including its purpose and key components."""
        summary_parts = []
        
        # Basic file information
        summary_parts.append(f"File: {self.file_path}")
        summary_parts.append(f"Type: {self.file_type}")
        summary_parts.append(f"Role: {'Entry Point' if self.is_entry_point else 'Core File' if self.is_core_file else 'Supporting File'}")
        
        # File purpose
        if self.purpose and self.purpose != "Purpose not explicitly documented.":
            summary_parts.append(f"Purpose: {self.purpose}")
        
        # Add detailed summary if available
        if self.detailed_summary:
            summary_parts.append("\nDetailed Analysis:")
            summary_parts.append(self.detailed_summary)
        
        # Method overview with detailed summaries
        if self.methods:
            summary_parts.append("\nKey Components:")
            for method in self.methods:
                method_summary = []
                method_summary.append(f"- {method['type'].title()} {method['name']}")
                
                # Add method parameters if available
                if 'parameters' in method:
                    method_summary.append(f"  Parameters: {method['parameters']}")
                
                # Add docstring if available
                if method['docstring']:
                    method_summary.append(f"  Purpose: {method['docstring']}")
                
                # Add detailed method summary if available
                if method['name'] in self.method_details:
                    method_summary.append(f"  Detailed Analysis: {self.method_details[method['name']]}")
                
                summary_parts.append("\n".join(method_summary))
        
        # Dependencies and relationships
        relationships = []
        if self.imports:
            relationships.append(f"Imports: {', '.join(self.imports)}")
        if self.imported_by:
            relationships.append(f"Used by: {', '.join(self.imported_by)}")
        if self.references:
            relationships.append(f"References: {', '.join(self.references)}")
        if self.referenced_by:
            relationships.append(f"Referenced by: {', '.join(self.referenced_by)}")
        
        if relationships:
            summary_parts.append("\nRelationships:")
            summary_parts.extend(relationships)
        
        return "\n".join(summary_parts)
    
    def _extract_keywords(self) -> List[str]:
        """Extract important keywords from the file content."""
        keywords = set()
        
        # Extract from docstrings and comments
        doc_patterns = [
            r'"""(.*?)"""',  # Python docstrings
            r'/\*\*(.*?)\*/',  # JSDoc comments
            r'#\s*(.*?)$'  # Single-line comments
        ]
        
        for pattern in doc_patterns:
            matches = re.finditer(pattern, self.content, re.MULTILINE)
            for match in matches:
                doc = match.group(1).strip()
                # Extract words that look like features or functionality
                words = re.findall(r'\b\w+(?:\s+\w+)*\b', doc)
                keywords.update(words)
        
        # Extract from function and class names
        name_patterns = [
            r'def\s+(\w+)',  # Python functions
            r'class\s+(\w+)',  # Classes
            r'function\s+(\w+)',  # JavaScript functions
            r'const\s+(\w+)',  # JavaScript constants
        ]
        
        for pattern in name_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                name = match.group(1)
                # Split camelCase and snake_case
                words = re.findall(r'[A-Z][a-z]+|[a-z]+', name)
                keywords.update(words)
        
        # Extract from variable names and assignments
        var_patterns = [
            r'(\w+)\s*=\s*[\'"]([^\'"]+)[\'"]',  # String assignments
            r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?',  # General assignments
        ]
        
        for pattern in var_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                var_name = match.group(1)
                value = match.group(2)
                # Add both variable name and value as keywords
                keywords.add(var_name)
                if len(value) > 3:  # Only add substantial values
                    keywords.add(value)
        
        # Extract from function parameters
        param_patterns = [
            r'def\s+\w+\s*\((.*?)\):',  # Python function parameters
            r'function\s+\w+\s*\((.*?)\)\s*{',  # JavaScript function parameters
        ]
        
        for pattern in param_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                params = match.group(1).strip()
                if params:
                    # Split parameters and extract names
                    param_names = [p.strip().split(':')[0].strip() for p in params.split(',')]
                    keywords.update(param_names)
        
        return list(keywords)
    
    def _extract_features(self) -> List[str]:
        """Extract features and functionality from the code."""
        features = set()
        
        # Look for feature indicators in docstrings and comments
        feature_patterns = [
            r'feature[s]?\s*:?\s*([^.!?]+)',
            r'functionality\s*:?\s*([^.!?]+)',
            r'capability\s*:?\s*([^.!?]+)',
            r'provides?\s*:?\s*([^.!?]+)',
            r'handles?\s*:?\s*([^.!?]+)',
            r'processes?\s*:?\s*([^.!?]+)',
            r'manages?\s*:?\s*([^.!?]+)',
            r'creates?\s*:?\s*([^.!?]+)',
            r'generates?\s*:?\s*([^.!?]+)',
            r'validates?\s*:?\s*([^.!?]+)',
            r'uploads?\s*:?\s*([^.!?]+)',
            r'downloads?\s*:?\s*([^.!?]+)',
            r'stores?\s*:?\s*([^.!?]+)',
            r'retrieves?\s*:?\s*([^.!?]+)',
            r'queries?\s*:?\s*([^.!?]+)',
            r'searches?\s*:?\s*([^.!?]+)',
            r'filters?\s*:?\s*([^.!?]+)',
            r'sorts?\s*:?\s*([^.!?]+)',
            r'analyzes?\s*:?\s*([^.!?]+)',
            r'processes?\s*:?\s*([^.!?]+)',
        ]
        
        for pattern in feature_patterns:
            matches = re.finditer(pattern, self.content, re.IGNORECASE)
            for match in matches:
                feature = match.group(1).strip()
                if len(feature) > 5:  # Only include substantial features
                    features.add(feature)
        
        # Look for feature indicators in function names
        function_patterns = [
            r'def\s+(\w+)\s*\(',  # Python functions
            r'function\s+(\w+)\s*\(',  # JavaScript functions
            r'const\s+(\w+)\s*=\s*function\s*\(',  # JavaScript arrow functions
        ]
        
        for pattern in function_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                name = match.group(1)
                # Convert camelCase and snake_case to readable features
                words = re.findall(r'[A-Z][a-z]+|[a-z]+', name)
                if len(words) > 1:  # Only include multi-word features
                    features.add(' '.join(words))
        
        # Look for file operations and API endpoints
        file_patterns = [
            r'open\s*\([\'"]([^\'"]+)[\'"]',  # File operations
            r'\.upload\s*\(',  # Upload operations
            r'\.download\s*\(',  # Download operations
            r'\.save\s*\(',  # Save operations
            r'\.read\s*\(',  # Read operations
            r'\.write\s*\(',  # Write operations
            r'\.delete\s*\(',  # Delete operations
            r'\.create\s*\(',  # Create operations
            r'\.update\s*\(',  # Update operations
        ]
        
        for pattern in file_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                if len(match.groups()) > 0:
                    feature = match.group(1)
                    if len(feature) > 5:
                        features.add(f"handles {feature}")
                else:
                    feature = pattern.replace(r'\\', '').replace(r'\(', '').replace(r'\)', '')
                    features.add(f"performs {feature}")
        
        # Look for API endpoints and routes
        route_patterns = [
            r'@app\.route\s*\([\'"]([^\'"]+)[\'"]',  # Flask routes
            r'router\.(get|post|put|delete)\s*\([\'"]([^\'"]+)[\'"]',  # Express routes
            r'@(Get|Post|Put|Delete)\s*\([\'"]([^\'"]+)[\'"]',  # NestJS routes
        ]
        
        for pattern in route_patterns:
            matches = re.finditer(pattern, self.content)
            for match in matches:
                if len(match.groups()) > 1:
                    method = match.group(1)
                    path = match.group(2)
                    features.add(f"provides {method.upper()} endpoint at {path}")
                else:
                    path = match.group(1)
                    features.add(f"provides endpoint at {path}")
        
        return list(features)

class SearchEngine:
    def __init__(self, llm_client=None):
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.graph = {}  # file_path -> CodeNode
            self.embeddings = {}  # file_path -> embedding
            self.codebase_purpose = None
            self.codebase_summary = None
            self.llm_client = llm_client
            logger.info("SearchEngine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing SearchEngine: {str(e)}")
            raise
    
    def build_graph(self, files_content: Dict[str, str]) -> None:
        """Build a rich graph representation of the codebase."""
        try:
            total_files = len(files_content)
            processed_files = 0
            failed_files = 0
            
            logger.info(f"Starting to build graph for {total_files} files")
            
            # First pass: Create nodes with detailed summaries
            for file_path, content in files_content.items():
                try:
                    # Skip empty files
                    if not content or not content.strip():
                        logger.warning(f"Skipping empty file: {file_path}")
                        failed_files += 1
                        continue
                        
                    # Skip binary files
                    if '\0' in content:
                        logger.warning(f"Skipping binary file: {file_path}")
                        failed_files += 1
                        continue
                    
                    self.graph[file_path] = CodeNode(file_path, content, self.llm_client)
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    logger.info(f"Progress: {progress:.1f}% - Created node for {file_path}")
                except Exception as e:
                    logger.error(f"Error creating node for {file_path}: {str(e)}")
                    failed_files += 1
                    continue
            
            if not self.graph:
                logger.error("No valid files were processed to create the graph")
                return
            
            logger.info(f"Completed first pass: {processed_files} files processed, {failed_files} files failed")
            
            # Second pass: Build relationships
            processed_files = 0
            failed_files = 0
            total_files = len(self.graph)
            
            for file_path, node in self.graph.items():
                try:
                    # Extract imports and references
                    if node.file_type == 'python':
                        import_lines = [line for line in node.content.split('\n') 
                                      if line.strip().startswith(('import ', 'from '))]
                        for line in import_lines:
                            try:
                                module = line.split()[1].split('.')[0]
                                for other_path in self.graph:
                                    if module in other_path:
                                        node.imports.add(other_path)
                                        self.graph[other_path].imported_by.add(file_path)
                            except Exception as e:
                                logger.error(f"Error processing import line '{line}' in {file_path}: {str(e)}")
                                continue
                    
                    elif node.file_type in ['typescript', 'javascript']:
                        import_lines = [line for line in node.content.split('\n') 
                                      if line.strip().startswith(('import ', 'require('))]
                        for line in import_lines:
                            try:
                                module = line.split()[1].strip("'\"")
                                for other_path in self.graph:
                                    if module in other_path:
                                        node.imports.add(other_path)
                                        self.graph[other_path].imported_by.add(file_path)
                            except Exception as e:
                                logger.error(f"Error processing import line '{line}' in {file_path}: {str(e)}")
                                continue
                    
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    logger.info(f"Progress: {progress:.1f}% - Built relationships for {file_path}")
                except Exception as e:
                    logger.error(f"Error building relationships for {file_path}: {str(e)}")
                    failed_files += 1
                    continue
            
            logger.info(f"Completed second pass: {processed_files} files processed, {failed_files} files failed")
            
            # Compute embeddings using detailed summaries
            processed_files = 0
            failed_files = 0
            
            for file_path, node in self.graph.items():
                try:
                    # Compute file-level embedding using detailed summary
                    summary_text = node.detailed_summary if node.detailed_summary else node.summary
                    if not summary_text or not summary_text.strip():
                        logger.warning(f"No valid summary text for {file_path}, using file content")
                        summary_text = node.content
                    
                    self.embeddings[file_path] = self.model.encode(summary_text)
                    
                    # Compute method-level embeddings using detailed summaries
                    for method in node.methods:
                        try:
                            method_context = node.method_details.get(method['name'], '') or node.method_summaries.get(method['name'], '')
                            if method_context and method_context.strip():
                                node.method_embeddings[method['name']] = self.model.encode(method_context)
                        except Exception as e:
                            logger.error(f"Error computing embedding for method {method['name']} in {file_path}: {str(e)}")
                            continue
                    
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    logger.info(f"Progress: {progress:.1f}% - Computed embeddings for {file_path}")
                except Exception as e:
                    logger.error(f"Error computing embeddings for {file_path}: {str(e)}")
                    failed_files += 1
                    continue
            
            logger.info(f"Completed third pass: {processed_files} files processed, {failed_files} files failed")
            
            # Analyze codebase
            self._analyze_codebase()
            logger.info("Graph built successfully")
        except Exception as e:
            logger.error(f"Error building graph: {str(e)}")
            raise
    
    def _analyze_codebase(self) -> None:
        """Analyze the overall purpose and structure of the codebase."""
        entry_points = [node for node in self.graph.values() if node.is_entry_point]
        core_files = [node for node in self.graph.values() if node.is_core_file]
        
        summary_parts = []
        
        # Overall statistics
        summary_parts.append("Codebase Overview:")
        summary_parts.append(f"Total Files: {len(self.graph)}")
        
        # File types
        file_types = {}
        for node in self.graph.values():
            file_types[node.file_type] = file_types.get(node.file_type, 0) + 1
        summary_parts.append("\nFile Types:")
        for ftype, count in file_types.items():
            summary_parts.append(f"- {ftype}: {count} files")
        
        # Entry points
        if entry_points:
            summary_parts.append("\nEntry Points:")
            for node in entry_points:
                summary_parts.append(f"- {node.file_path}")
                if node.purpose != "Purpose not explicitly documented.":
                    summary_parts.append(f"  Purpose: {node.purpose}")
        
        # Core components
        if core_files:
            summary_parts.append("\nCore Components:")
            for node in core_files:
                summary_parts.append(f"- {node.file_path}")
                if node.purpose != "Purpose not explicitly documented.":
                    summary_parts.append(f"  Purpose: {node.purpose}")
        
        self.codebase_summary = "\n".join(summary_parts)
        
        # Set codebase purpose
        purpose_parts = []
        for node in entry_points + core_files:
            if node.purpose != "Purpose not explicitly documented.":
                purpose_parts.append(node.purpose)
        
        self.codebase_purpose = "\n\n".join(purpose_parts) if purpose_parts else "Purpose not explicitly documented in the codebase."
    
    def get_codebase_overview(self) -> Dict[str, Any]:
        """Get a comprehensive overview of the codebase."""
        return {
            "summary": self.codebase_summary,
            "purpose": self.codebase_purpose,
            "total_files": len(self.graph),
            "entry_points": [node.file_path for node in self.graph.values() if node.is_entry_point],
            "core_files": [node.file_path for node in self.graph.values() if node.is_core_file]
        }
    
    def find_relevant_files(self, query: str, max_files: int = 5) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """Find relevant files and return their enriched content."""
        if not self.graph:
            return [], {}
        
        query_embedding = self.model.encode(query)
        
        # Calculate initial relevance scores
        file_scores = {}
        for file_path, node in self.graph.items():
            # File-level similarity using detailed summary
            summary_text = node.detailed_summary if node.detailed_summary else node.summary
            file_similarity = cosine_similarity([query_embedding], [self.model.encode(summary_text)])[0][0]
            
            # Method-level similarity using detailed summaries
            method_similarities = []
            for method in node.methods:
                method_context = node.method_details.get(method['name'], '') or node.method_summaries.get(method['name'], '')
                if method_context:
                    method_similarity = cosine_similarity([query_embedding], [self.model.encode(method_context)])[0][0]
                    method_similarities.append(method_similarity)
            
            # Feature-based relevance
            feature_similarity = 0
            if node.features:
                feature_embeddings = [self.model.encode(feature) for feature in node.features]
                feature_similarities = [cosine_similarity([query_embedding], [fe])[0][0] for fe in feature_embeddings]
                feature_similarity = max(feature_similarities) if feature_similarities else 0
            
            # Keyword-based relevance
            keyword_similarity = 0
            if node.keywords:
                keyword_embeddings = [self.model.encode(keyword) for keyword in node.keywords]
                keyword_similarities = [cosine_similarity([query_embedding], [ke])[0][0] for ke in keyword_embeddings]
                keyword_similarity = max(keyword_similarities) if keyword_similarities else 0
            
            # Purpose-based relevance
            purpose_similarity = 0
            if node.purpose and node.purpose != "Purpose not explicitly documented.":
                purpose_embedding = self.model.encode(node.purpose)
                purpose_similarity = cosine_similarity([query_embedding], [purpose_embedding])[0][0]
            
            # Combine scores with weights
            max_method_similarity = max(method_similarities) if method_similarities else 0
            file_scores[file_path] = (
                0.3 * file_similarity +
                0.2 * max_method_similarity +
                0.2 * feature_similarity +
                0.15 * keyword_similarity +
                0.15 * purpose_similarity
            )
        
        # Get initial set of relevant files
        initial_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)[:max_files]
        relevant_files = [file_path for file_path, _ in initial_files]
        
        # Expand relevant files based on relationships
        expanded_files = set(relevant_files)
        for file_path in relevant_files:
            node = self.graph[file_path]
            # Add files that import this file
            expanded_files.update(node.imported_by)
            # Add files that this file imports
            expanded_files.update(node.imports)
            # Add files that reference this file
            expanded_files.update(node.referenced_by)
            # Add files that this file references
            expanded_files.update(node.references)
        
        # Limit expanded set to top files
        expanded_files = list(expanded_files)[:max_files * 2]
        
        # Prepare enriched content with context
        relevant_content = {}
        for file_path in expanded_files:
            node = self.graph[file_path]
            
            # Basic file information
            file_info = {
                "content": node.content,
                "summary": node.summary,
                "detailed_summary": node.detailed_summary,
                "type": node.file_type,
                "is_entry_point": node.is_entry_point,
                "is_core_file": node.is_core_file,
                "purpose": node.purpose,
                "features": node.features,
                "keywords": node.keywords,
                "methods": []
            }
            
            # Add method information with detailed summaries
            for method in node.methods:
                method_info = {
                    "name": method["name"],
                    "type": method["type"],
                    "summary": node.method_summaries.get(method["name"], ""),
                    "detailed_summary": node.method_details.get(method["name"], ""),
                    "docstring": method["docstring"],
                    "body": method["body"]
                }
                file_info["methods"].append(method_info)
            
            # Add relationship information
            file_info["relationships"] = {
                "imports": list(node.imports),
                "imported_by": list(node.imported_by),
                "references": list(node.references),
                "referenced_by": list(node.referenced_by)
            }
            
            relevant_content[file_path] = file_info
        
        logger.info(f"Found {len(expanded_files)} relevant files using semantic search")
        return expanded_files, relevant_content
    
    def get_file_summary(self, file_path: str, content: str) -> str:
        """Generate a concise summary of a file's content."""
        # Get first few lines and last few lines
        lines = content.split('\n')
        if len(lines) <= 10:
            return content
        
        summary = f"File: {file_path}\n"
        summary += "First few lines:\n"
        summary += '\n'.join(lines[:5])
        summary += "\n\nLast few lines:\n"
        summary += '\n'.join(lines[-5:])
        return summary 