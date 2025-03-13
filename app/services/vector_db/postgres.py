import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, NamedTuple, Optional

import numpy as np
import psycopg2
import psycopg2.extras

from app.core.config import settings
from app.services.vector_db.base import VectorDBService

logger = logging.getLogger(__name__)

class PGSearchResult(NamedTuple):
    """Standard search result structure"""
    id: str
    score: float
    payload: Dict[str, Any]

class PostgresVectorDBService(VectorDBService):
    """PostgreSQL with pgvector implementation of VectorDBService"""
    
    def __init__(self):
        self.conn_params = {
            'dbname': settings.DB_NAME,
            'user': settings.DB_USER,
            'password': settings.DB_PASSWORD,
            'host': settings.DB_HOST,
            'port': settings.DB_PORT
        }
        self.table_name = "image_embeddings"
        self.vector_size = settings.VECTOR_SIZE
        self.instance_connection_name = settings.INSTANCE_CONNECTION_NAME
    
    @contextmanager
    def get_connection(self):
        """Create and return a database connection"""
        # Check if we're running with Cloud SQL Proxy
        instance_connection_name = os.environ.get('INSTANCE_CONNECTION_NAME')
        
        try:
            if self.instance_connection_name and os.path.exists('/tmp/cloudsql'):
                # Using Cloud SQL Proxy with unix socket
                unix_socket = f'/tmp/cloudsql/{self.instance_connection_name}'
                logger.info(f"Connecting to PostgreSQL via Cloud SQL Proxy at {unix_socket}")
                
                conn = psycopg2.connect(
                    dbname=self.conn_params.get('dbname'),
                    user=self.conn_params.get('user'),
                    password=self.conn_params.get('password'),
                    host=unix_socket  # This is the key difference
                )
                logger.info("Successfully connected to PostgreSQL via Cloud SQL Proxy")
            else:
                # Regular connection for local development
                logger.info(f"Connecting to PostgreSQL at {self.conn_params.get('host')}:{self.conn_params.get('port')}")
                conn = psycopg2.connect(**self.conn_params)
                logger.info("Successfully connected to PostgreSQL via direct connection")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
            # Log more details to help diagnose
            logger.error(f"Connection params: host={self.conn_params.get('host', 'None')}, "
                        f"port={self.conn_params.get('port', 'None')}, "
                        f"dbname={self.conn_params.get('dbname', 'None')}, "
                        f"user={self.conn_params.get('user', 'None')}")
            logger.error(f"INSTANCE_CONNECTION_NAME: {instance_connection_name}")
            logger.error(f"Socket directory exists: {os.path.exists('/tmp/cloudsql')}")
            if instance_connection_name:
                logger.error(f"Socket path: /tmp/cloudsql/{instance_connection_name}")
                logger.error(f"Socket exists: {os.path.exists(f'/tmp/cloudsql/{instance_connection_name}')}")
            raise
        
        try:
            yield conn
        finally:
            conn.close()
    
    async def initialize(self):
        """Initialize the PostgreSQL connection and create table with pgvector extension"""
        try:
            logger.info(f"Initializing PostgreSQL connection to {self.conn_params['host']}:{self.conn_params['port']}")
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create pgvector extension if it doesn't exist
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    
                    # Create table if it doesn't exist
                    cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id TEXT PRIMARY KEY,
                        filename TEXT,
                        upload_time TIMESTAMP,
                        embedding vector({self.vector_size}),
                        metadata JSONB
                    );
                    """)
                    
                    # Create an index for faster search
                    cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS embedding_idx 
                    ON {self.table_name} USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                    """)
                    
                    # Get row count for logging
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    count = cur.fetchone()[0]
                    
                    conn.commit()
                    
                    logger.info(f"PostgreSQL table {self.table_name} initialized with pgvector. Contains {count} rows.")
        except Exception as e:
            logger.error(f"Error initializing PostgreSQL: {e}")
            raise
    
    def store_embedding(self, id: str, vector: np.ndarray, metadata: Dict[str, Any] = None):
        """Store an embedding in PostgreSQL with pgvector"""
        if metadata is None:
            metadata = {}
        
        # Extract common metadata fields
        filename = metadata.pop("filename", "") if metadata else ""
        upload_time = metadata.pop("upload_time", time.time()) if metadata else time.time()
        
        # Convert timestamp to datetime
        if isinstance(upload_time, (int, float)):
            from datetime import datetime
            upload_time = datetime.fromtimestamp(upload_time)
        
        # Always normalize the vector (critical for consistent search)
        vector_norm = np.linalg.norm(vector)
        if vector_norm > 0:
            vector = vector / vector_norm
        
        logger.info(f"Storing embedding for {id}, norm after normalization: {np.linalg.norm(vector):.4f}")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use pgvector's vector casting
                    cur.execute(
                        f"""
                        INSERT INTO {self.table_name} (id, filename, upload_time, embedding, metadata)
                        VALUES (%s, %s, %s, %s::vector, %s)
                        ON CONFLICT (id) DO UPDATE
                        SET filename = EXCLUDED.filename,
                            upload_time = EXCLUDED.upload_time,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata;
                        """,
                        (
                            id,
                            filename,
                            upload_time,
                            vector.tolist(),
                            psycopg2.extras.Json(metadata)
                        )
                    )
                    conn.commit()
                    logger.info(f"Successfully stored embedding for {id} ({filename})")
        except Exception as e:
            logger.error(f"Error storing embedding in PostgreSQL: {e}")
            raise
    
    def search_similar(self, vector: np.ndarray, limit: int = 5) -> List[Any]:
        """
        Search for similar vectors in PostgreSQL using pgvector cosine similarity
        """
        try:
            # Always ensure the vector is normalized
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
                
            # Log the first few values for debugging
            logger.info(f"Search vector stats: shape={vector.shape}, norm={np.linalg.norm(vector):.4f}")
            logger.debug(f"Search vector start: {vector[:5]}")
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # Check if we have data
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    count = cur.fetchone()[0]
                    logger.info(f"Found {count} rows in database")
                    
                    # Exit early if no data
                    if count == 0:
                        logger.warning("No data in database - search will return empty results")
                        return []
                    
                    # Execute a simple test query first to validate the approach
                    test_query = f"""
                    SELECT id, 1 - (embedding <=> %s::vector) as similarity_score
                    FROM {self.table_name}
                    LIMIT 1;
                    """
                    cur.execute(test_query, (vector.tolist(),))
                    test_result = cur.fetchone()
                    logger.debug(f"Test query result: {test_result}")
                    
                    # Now execute the actual search query
                    query = f"""
                    SELECT id, filename, upload_time, metadata,
                           1 - (embedding <=> %s::vector) as similarity_score
                    FROM {self.table_name}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """
                    
                    # Execute with vector list
                    vector_list = vector.tolist()
                    cur.execute(query, (vector_list, vector_list, limit))
                    
                    # Get and process results
                    rows = cur.fetchall()
                    logger.info(f"Search returned {len(rows)} rows with {limit} requested")
                    
                    # Log the first result details
                    if rows:
                        logger.info(f"Top result: id={rows[0]['id']}, score={rows[0]['similarity_score']}")
                    
                    # Process results
                    search_results = []
                    for row in rows:
                        similarity = float(row['similarity_score'])
                        if similarity <= 0:
                            logger.warning(f"Unusually low similarity score: {similarity}")
                        
                        result = PGSearchResult(
                            id=row['id'],
                            score=similarity,
                            payload={
                                "filename": row['filename'],
                                "upload_time": row['upload_time'].timestamp() if row['upload_time'] else None,
                                **(row['metadata'] or {})
                            }
                        )
                        search_results.append(result)
                    
                    return search_results
        except Exception as e:
            logger.error(f"Error searching in PostgreSQL: {e}")
            raise
    
    def bulk_store_embeddings(self, embeddings_data: List[Dict]):
        """
        Store multiple embeddings in the PostgreSQL database efficiently
        
        Args:
            embeddings_data: List of dictionaries containing:
                - id: Unique identifier for the image
                - vector: The embedding vector (numpy array)
                - metadata: Dictionary with metadata like filename, url, etc.
        """
        if not embeddings_data:
            logger.warning("No embeddings provided for bulk storage")
            return
        
        start_time = time.time()
        logger.info(f"Starting bulk storage of {len(embeddings_data)} embeddings")
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create a batch insert query
                    args = []
                    values_template = []
                    
                    for i, item in enumerate(embeddings_data):
                        image_id = item['id']
                        vector = item['vector']
                        metadata = item.get('metadata', {})
                        
                        # Extract common metadata fields
                        filename = metadata.pop("filename", "") if metadata else ""
                        upload_time = metadata.pop("upload_time", time.time()) if metadata else time.time()
                        
                        # Convert timestamp to datetime
                        if isinstance(upload_time, (int, float)):
                            from datetime import datetime
                            upload_time = datetime.fromtimestamp(upload_time)
                        
                        # Always normalize the vector (important for consistent similarity)
                        vector_norm = np.linalg.norm(vector)
                        if vector_norm > 0:
                            vector = vector / vector_norm
                        
                        # Add to batch
                        values_template.append("(%s, %s, %s, %s::vector, %s)")
                        args.extend([
                            image_id,
                            filename,
                            upload_time,
                            vector.tolist(),
                            psycopg2.extras.Json(metadata)
                        ])
                    
                    # Execute the batch insert
                    values_str = ", ".join(values_template)
                    query = f"""
                    INSERT INTO {self.table_name} (id, filename, upload_time, embedding, metadata)
                    VALUES {values_str}
                    ON CONFLICT (id) DO UPDATE
                    SET filename = EXCLUDED.filename,
                        upload_time = EXCLUDED.upload_time,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata;
                    """
                    cur.execute(query, args)
                    conn.commit()
                    
                    logger.info(f"Bulk storage completed in {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error during bulk storage in PostgreSQL: {e}")
            raise
    
    def get_metadata_by_id(self, id: str) -> Dict[str, Any]:
        """Get metadata for a specific embedding by ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        f"SELECT filename, metadata FROM {self.table_name} WHERE id = %s",
                        (id,)
                    )
                    row = cur.fetchone()
                    if row:
                        result = {"filename": row['filename']}
                        # Add metadata fields if available
                        if row['metadata']:
                            result.update(row['metadata'])
                        return result
                    raise ValueError(f"No metadata found for ID {id}")
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            raise

    def get_embedding_by_id(self, id: str) -> Optional[np.ndarray]:
        """Get a specific embedding by ID for debugging"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT embedding FROM {self.table_name} WHERE id = %s",
                        (id,)
                    )
                    row = cur.fetchone()
                    if row:
                        # Convert from PostgreSQL array format to numpy
                        return np.array(row[0])
                    return None
        except Exception as e:
            logger.error(f"Error getting embedding by ID {id}: {e}")
            return None
    
    def get_name(self) -> str:
        """Get the name of this vector DB implementation"""
        return "postgres"

# Create a global instance
postgres_service = PostgresVectorDBService()