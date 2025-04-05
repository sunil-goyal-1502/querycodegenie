import sqlite3
import json
import os
import logging
from typing import Dict, List, Optional, Any, Union
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    """Database class for storing codebase information."""
    
    def __init__(self, db_path: str = "codebase.db"):
        """Initialize the database."""
        self.db_path = db_path
        self._local = threading.local()
        self.logger = logging.getLogger(__name__)
        self._init_db()
    
    def _get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._local.connection
    
    def _init_db(self):
        """Initialize the database tables."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create files table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                language TEXT,
                file_hash TEXT,
                summary TEXT,
                detailed_summary TEXT,
                is_entry_point BOOLEAN,
                is_core_file BOOLEAN,
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create methods table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                method_name TEXT,
                method_type TEXT,
                line_numbers TEXT,
                summary TEXT,
                FOREIGN KEY (file_path) REFERENCES files (file_path)
            )
            ''')
            
            # Create relationships table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT,
                target_file TEXT,
                relationship_type TEXT,
                FOREIGN KEY (source_file) REFERENCES files (file_path),
                FOREIGN KEY (target_file) REFERENCES files (file_path)
            )
            ''')
            
            # Check if indexing_status table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='indexing_status'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # Create indexing_status table with all columns
                cursor.execute('''
                CREATE TABLE indexing_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_files INTEGER,
                    processed_files INTEGER,
                    failed_files INTEGER,
                    success_rate REAL,
                    file_types TEXT,
                    languages TEXT,
                    indexed_files TEXT,
                    failed_files_details TEXT,
                    is_complete BOOLEAN,
                    is_loading BOOLEAN,
                    repo_url TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
            else:
                # Check existing columns
                cursor.execute("PRAGMA table_info(indexing_status)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # Add missing columns if they don't exist
                if 'indexed_files' not in columns:
                    self.logger.info("Adding indexed_files column to indexing_status table")
                    cursor.execute("ALTER TABLE indexing_status ADD COLUMN indexed_files TEXT")
                
                if 'failed_files_details' not in columns:
                    self.logger.info("Adding failed_files_details column to indexing_status table")
                    cursor.execute("ALTER TABLE indexing_status ADD COLUMN failed_files_details TEXT")
                
                if 'last_updated' not in columns:
                    self.logger.info("Adding last_updated column to indexing_status table")
                    cursor.execute("ALTER TABLE indexing_status ADD COLUMN last_updated TIMESTAMP")
            
            conn.commit()
            self.logger.info("Database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            raise
    
    def save_file(self, file_path: str, language: str, file_hash: str, summary: str, detailed_summary: str, is_entry_point: bool, is_core_file: bool):
        """Save file metadata to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO files (file_path, language, file_hash, summary, detailed_summary, is_entry_point, is_core_file, last_indexed)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (file_path, language, file_hash, summary, detailed_summary, is_entry_point, is_core_file))
        
        conn.commit()
    
    def save_method(self, file_path: str, method_name: str, method_type: str, line_numbers: Dict[str, int], summary: str):
        """Save method metadata to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO methods (file_path, method_name, method_type, line_numbers, summary)
        VALUES (?, ?, ?, ?, ?)
        ''', (file_path, method_name, method_type, json.dumps(line_numbers), summary))
        
        conn.commit()
    
    def save_relationship(self, source_file: str, target_file: str, relationship_type: str):
        """Save file relationship to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO relationships (source_file, target_file, relationship_type)
        VALUES (?, ?, ?)
        ''', (source_file, target_file, relationship_type))
        
        conn.commit()
    
    def update_indexing_status(
        self,
        total_files: int,
        processed_files: int,
        failed_files: int,
        success_rate: float,
        file_types: Dict[str, int],
        languages: Dict[str, int],
        indexed_files: List[str] = None,
        failed_files_details: List[Dict[str, str]] = None,
        is_complete: bool = False,
        is_loading: bool = False,
        repo_url: str = None
    ) -> None:
        """Update the indexing status in the database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Convert dictionaries to JSON strings
            file_types_json = json.dumps(file_types)
            languages_json = json.dumps(languages)
            indexed_files_json = json.dumps(indexed_files or [])
            failed_files_details_json = json.dumps(failed_files_details or [])
            
            # Update or insert indexing status
            cursor.execute("""
                INSERT OR REPLACE INTO indexing_status (
                    id,
                    total_files,
                    processed_files,
                    failed_files,
                    success_rate,
                    file_types,
                    languages,
                    indexed_files,
                    failed_files_details,
                    is_complete,
                    is_loading,
                    repo_url,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1,  # Use a single row for status
                total_files,
                processed_files,
                failed_files,
                success_rate,
                file_types_json,
                languages_json,
                indexed_files_json,
                failed_files_details_json,
                is_complete,
                is_loading,
                repo_url,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            self.logger.info(f"Updated indexing status: {processed_files}/{total_files} files processed")
            
        except Exception as e:
            self.logger.error(f"Error updating indexing status: {str(e)}")
            raise
    
    def get_indexing_status(self, repo_url: Optional[str] = None) -> Dict[str, Any]:
        """Get the latest indexing status from the database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if repo_url:
                cursor.execute('''
                SELECT total_files, processed_files, failed_files, success_rate, 
                       file_types, languages, indexed_files, failed_files_details,
                       is_complete, is_loading, repo_url, last_updated
                FROM indexing_status
                WHERE repo_url = ?
                ORDER BY last_updated DESC
                LIMIT 1
                ''', (repo_url,))
            else:
                cursor.execute('''
                SELECT total_files, processed_files, failed_files, success_rate,
                       file_types, languages, indexed_files, failed_files_details,
                       is_complete, is_loading, repo_url, last_updated
                FROM indexing_status
                ORDER BY last_updated DESC
                LIMIT 1
                ''')
            
            row = cursor.fetchone()
            if row:
                return {
                    'total_files': row[0],
                    'processed_files': row[1],
                    'failed_files': row[2],
                    'success_rate': row[3],
                    'file_types': json.loads(row[4]) if row[4] else {},
                    'languages': json.loads(row[5]) if row[5] else {},
                    'indexed_files': json.loads(row[6]) if row[6] else [],
                    'failed_files_details': json.loads(row[7]) if row[7] else [],
                    'is_complete': bool(row[8]),
                    'is_loading': bool(row[9]),
                    'repo_url': row[10],
                    'last_updated': row[11]
                }
            
            # Return default values if no status found
            return {
                'total_files': 0,
                'processed_files': 0,
                'failed_files': 0,
                'success_rate': 0.0,
                'file_types': {},
                'languages': {},
                'indexed_files': [],
                'failed_files_details': [],
                'is_complete': False,
                'is_loading': False,
                'repo_url': None,
                'last_updated': None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting indexing status: {str(e)}")
            # Return default values on error
            return {
                'total_files': 0,
                'processed_files': 0,
                'failed_files': 0,
                'success_rate': 0.0,
                'file_types': {},
                'languages': {},
                'indexed_files': [],
                'failed_files_details': [],
                'is_complete': False,
                'is_loading': False,
                'repo_url': None,
                'last_updated': None
            }
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT file_path, language, file_hash, summary, detailed_summary, is_entry_point, is_core_file, last_indexed
        FROM files
        WHERE file_path = ?
        ''', (file_path,))
        
        row = cursor.fetchone()
        if row:
            return {
                'file_path': row[0],
                'language': row[1],
                'file_hash': row[2],
                'summary': row[3],
                'detailed_summary': row[4],
                'is_entry_point': row[5],
                'is_core_file': row[6],
                'last_indexed': row[7]
            }
        return None
    
    def get_file_methods(self, file_path: str) -> List[Dict[str, Any]]:
        """Get methods for a file from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT method_name, method_type, line_numbers, summary
        FROM methods
        WHERE file_path = ?
        ''', (file_path,))
        
        methods = []
        for row in cursor.fetchall():
            methods.append({
                'name': row[0],
                'type': row[1],
                'line_numbers': json.loads(row[2]),
                'summary': row[3]
            })
        return methods
    
    def get_file_relationships(self, file_path: str) -> List[Dict[str, str]]:
        """Get relationships for a file from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT source_file, target_file, relationship_type
        FROM relationships
        WHERE source_file = ? OR target_file = ?
        ''', (file_path, file_path))
        
        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                'source_file': row[0],
                'target_file': row[1],
                'relationship_type': row[2]
            })
        return relationships
    
    def needs_reindexing(self, file_path: str, file_hash: str) -> bool:
        """Check if a file needs reindexing based on its hash."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT file_hash
        FROM files
        WHERE file_path = ?
        ''', (file_path,))
        
        row = cursor.fetchone()
        if not row:
            return True
        
        return row[0] != file_hash
    
    def reset_indexing_status(self) -> None:
        """Reset the indexing status table."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Drop and recreate the indexing_status table
            cursor.execute("DROP TABLE IF EXISTS indexing_status")
            
            # Recreate the table with the latest schema
            cursor.execute('''
            CREATE TABLE indexing_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_files INTEGER,
                processed_files INTEGER,
                failed_files INTEGER,
                success_rate REAL,
                file_types TEXT,
                languages TEXT,
                indexed_files TEXT,
                failed_files_details TEXT,
                is_complete BOOLEAN,
                is_loading BOOLEAN,
                repo_url TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Insert initial row with current timestamp
            cursor.execute('''
            INSERT INTO indexing_status (
                total_files, processed_files, failed_files, success_rate,
                file_types, languages, indexed_files, failed_files_details,
                is_complete, is_loading, repo_url, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                0, 0, 0, 0.0,
                '{}', '{}', '[]', '[]',
                False, False, None, datetime.now().isoformat()
            ))
            
            conn.commit()
            self.logger.info("Indexing status table reset successfully")
            
        except Exception as e:
            self.logger.error(f"Error resetting indexing status: {str(e)}")
            raise 