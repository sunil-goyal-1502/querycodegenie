import numpy as np
import faiss
import json
import os
from typing import Dict, List, Optional, Tuple, Any
import logging
from sentence_transformers import SentenceTransformer

class VectorDB:
    def __init__(self, db_path: str = "vector_index"):
        self.db_path = db_path
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast and effective model for embeddings
        self.dimension = 384  # Dimension of embeddings from the model
        self.index = None
        self.metadata = []
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create a new one."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.db_path, exist_ok=True)
            
            # Initialize metadata file if it doesn't exist or is corrupted
            metadata_path = os.path.join(self.db_path, "metadata.json")
            if not os.path.exists(metadata_path):
                self._save_metadata()
            else:
                try:
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                    # Validate metadata structure
                    if not isinstance(self.metadata, list):
                        self.logger.warning("Invalid metadata structure, reinitializing")
                        self.metadata = []
                        self._save_metadata()
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"Error loading metadata: {str(e)}, reinitializing")
                    self.metadata = []
                    self._save_metadata()
            
            # Initialize or load FAISS index
            index_path = os.path.join(self.db_path, "index.faiss")
            if os.path.exists(index_path):
                try:
                    self.index = faiss.read_index(index_path)
                    self.logger.info(f"Loaded existing vector index with {len(self.metadata)} entries")
                except Exception as e:
                    self.logger.warning(f"Error loading FAISS index: {str(e)}, creating new index")
                    self.index = faiss.IndexFlatL2(self.dimension)
            else:
                self.index = faiss.IndexFlatL2(self.dimension)
                self.logger.info("Created new vector index")
                
        except Exception as e:
            self.logger.error(f"Error in _load_or_create_index: {str(e)}")
            # Initialize with empty state
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            self._save_metadata()
    
    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            metadata_path = os.path.join(self.db_path, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metadata: {str(e)}")
    
    def _save_index(self):
        """Save FAISS index to disk."""
        try:
            index_path = os.path.join(self.db_path, "index.faiss")
            faiss.write_index(self.index, index_path)
        except Exception as e:
            self.logger.error(f"Error saving FAISS index: {str(e)}")
    
    def add_file(self, file_path: str, content: str, language: str, summary: str, detailed_summary: str, methods: List[Dict[str, Any]], imports: List[str]):
        """Add a file to the vector database."""
        try:
            # Create embeddings for file-level content
            file_embedding = self.model.encode([content])[0]
            
            # Create embeddings for methods
            method_embeddings = []
            method_metadata = []
            
            for method in methods:
                method_text = f"{method['name']} ({method['type']}): {method['summary']}"
                method_embedding = self.model.encode([method_text])[0]
                method_embeddings.append(method_embedding)
                method_metadata.append({
                    'file_path': file_path,
                    'method_name': method['name'],
                    'method_type': method['type'],
                    'line_numbers': method['line_numbers'],
                    'summary': method['summary']
                })
            
            # Add file embedding to index
            self.index.add(np.array([file_embedding], dtype=np.float32))
            
            # Add method embeddings to index
            if method_embeddings:
                self.index.add(np.array(method_embeddings, dtype=np.float32))
            
            # Update metadata
            self.metadata.append({
                'id': len(self.metadata),
                'file_path': file_path,
                'language': language,
                'summary': summary,
                'detailed_summary': detailed_summary,
                'is_method': False
            })
            
            # Add method metadata
            for i, metadata in enumerate(method_metadata):
                self.metadata.append({
                    'id': len(self.metadata),
                    'file_path': metadata['file_path'],
                    'method_name': metadata['method_name'],
                    'method_type': metadata['method_type'],
                    'line_numbers': metadata['line_numbers'],
                    'summary': metadata['summary'],
                    'is_method': True
                })
            
            # Save the updated index and metadata
            self._save_index()
            self._save_metadata()
            
            return True
        except Exception as e:
            self.logger.error(f"Error adding file to vector database: {str(e)}")
            return False
    
    def search(self, query: str, k: int = 5) -> List[Dict[str, any]]:
        """Search for relevant code snippets and methods."""
        try:
            # Create query embedding
            query_embedding = self.model.encode([query])[0]
            
            # Search the index
            distances, indices = self.index.search(
                np.array([query_embedding]).astype('float32'), k
            )
            
            # Get results with metadata
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.metadata):
                    result = self.metadata[idx].copy()
                    result['relevance_score'] = float(1 / (1 + distances[0][i]))  # Convert distance to similarity score
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching vector database: {str(e)}")
            return []
    
    def get_file_content(self, file_path: str) -> Optional[Dict[str, any]]:
        """Get all embeddings and metadata for a file."""
        try:
            file_entries = [entry for entry in self.metadata if entry['file_path'] == file_path]
            if not file_entries:
                return None
            
            # Find the file-level entry
            file_entry = next((entry for entry in file_entries if entry['type'] == 'file'), None)
            if not file_entry:
                return None
            
            # Get all method entries
            method_entries = [entry for entry in file_entries if entry['type'] == 'method']
            
            return {
                "file_path": file_path,
                "content": file_entry['content'],
                "summary": file_entry['summary'],
                "detailed_summary": file_entry['detailed_summary'],
                "methods": method_entries
            }
            
        except Exception as e:
            self.logger.error(f"Error getting file content from vector database: {str(e)}")
            return None
    
    def add_document(self, file_path: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Add a document to the vector database."""
        try:
            # Validate inputs
            if not file_path:
                self.logger.error("File path is required")
                return False
                
            if not content:
                self.logger.warning(f"No content provided for file {file_path}, using empty string")
                content = ""
                
            if not metadata:
                self.logger.warning(f"No metadata provided for file {file_path}")
                metadata = {}
            
            # Create embedding for the content
            embedding = self.model.encode([content])[0]
            
            # Add embedding to index
            self.index.add(np.array([embedding], dtype=np.float32))
            
            # Update metadata
            self.metadata.append({
                'id': len(self.metadata),
                'file_path': file_path,
                'content': content,
                'type': metadata.get('type', 'file'),
                **metadata
            })
            
            # Save the updated index and metadata
            self._save_index()
            self._save_metadata()
            
            return True
        except Exception as e:
            self.logger.error(f"Error adding document to vector database: {str(e)}")
            return False 