import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, NamedTuple, Optional

import numpy as np
import sqlalchemy
from sqlalchemy.pool import NullPool
from google.cloud.alloydb.connector import Connector  # Removed ConnectorConfig
import pg8000.native  # Required by the AlloyDB connector

from app.core.config import settings
from app.services.vector_db.base import VectorDBService

logger = logging.getLogger(__name__)

class AlloyDBSearchResult(NamedTuple):
    """Standard search result structure"""
    id: str
    score: float
    payload: Dict[str, Any]

class AlloyDBVectorService(VectorDBService):
    """AlloyDB with pgvector implementation of VectorDBService"""
    
    def __init__(self):
        self.db_user = settings.ALLOYDB_USER
        self.db_pass = settings.ALLOYDB_PASSWORD
        self.db_name = settings.ALLOYDB_NAME
        self.instance_uri = settings.ALLOYDB_INSTANCE_CONNECTION_NAME
        self.table_name = "image_embeddings"
        self.vector_size = settings.VECTOR_SIZE
        
        # Initialize connector for AlloyDB
        self.connector = Connector()
        # Removed ConnectorConfig
        
        # Initialize engine lazily
        self._engine = None
        
    def get_engine(self):
        """Get or create SQLAlchemy engine with connection pool"""
        if self._engine is None:
            def getconn():
                try:
                    conn = self.connector.connect(
                        self.instance_uri,
                        "pg8000",
                        user=self.db_user,
                        password=self.db_pass,
                        db=self.db_name,
                        ip_type="PUBLIC",
                        timeout=10  # Add a timeout to the initial connection attempt
                    )
                    logger.info(f"Successfully connected to AlloyDB via connector")
                    return conn
                except Exception as e:
                    logger.error(f"Failed to connect to AlloyDB: {str(e)}")
                    raise
            
            # Create connection pool with SQLAlchemy
            self._engine = sqlalchemy.create_engine(
                "postgresql+pg8000://",
                creator=getconn,
                # Configure pooling based on your requirements
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,  # Recycle connections after 30 minutes
                connect_args={  # Add connect args for socket timeout
                    'options': '-c tcp_keepalives_idle=60 -c tcp_keepalives_interval=10 -c tcp_keepalives_count=3 -c statement_timeout=60s'
                }
            )
            logger.info("Initialized AlloyDB connection pool")
        
        return self._engine
    
    @contextmanager
    def get_connection(self):
        """Create and return a SQLAlchemy connection"""
        engine = self.get_engine()
        connection = None
        try:
            connection = engine.connect()
            yield connection
        except Exception as e:
            logger.error(f"Error with AlloyDB connection: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    async def initialize(self):
        """Initialize the AlloyDB connection and create table with pgvector extension"""
        try:
            logger.info(f"Initializing AlloyDB connection to {self.instance_uri}")
            
            with self.get_connection() as conn:
                # Create pgvector extension if it doesn't exist
                conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector;"))
                
                # Create table if it doesn't exist
                create_table_sql = sqlalchemy.text(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id TEXT PRIMARY KEY,
                    filename TEXT,
                    upload_time TIMESTAMP,
                    embedding vector({self.vector_size}),
                    product_description TEXT,
                    product_reviews TEXT,
                    metadata JSONB     
                );
                """)
                conn.execute(create_table_sql)
                
                # Create an index for faster search - using HNSW index for better performance
                create_index_sql = sqlalchemy.text(f"""
                CREATE INDEX IF NOT EXISTS embedding_hnsw_idx 
                ON {self.table_name} USING hnsw (embedding vector_cosine_ops)
                WITH (ef_construction = 128, m = 16);
                """)
                conn.execute(create_index_sql)
                
                # Get row count for logging
                result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {self.table_name}"))
                count = result.scalar()
                
                # Commit the transaction
                conn.commit()
                
                logger.info(f"AlloyDB table {self.table_name} initialized with pgvector. Contains {count} rows.")
        except Exception as e:
            logger.error(f"Error initializing AlloyDB: {e}")
            raise
    
    def store_embedding(self, id: str, vector: np.ndarray, metadata: Dict[str, Any] = None):
        """Store an embedding in AlloyDB with pgvector"""
        if metadata is None:
            metadata = {}
        
        # Extract common metadata fields
        filename = metadata.pop("filename", "") if metadata else ""
        product_description = metadata.pop("product_description", "") if metadata else ""
        product_reviews = metadata.pop("product_reviews", "") if metadata else ""
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
                # Convert metadata to JSON string
                metadata_json = sqlalchemy.JSON.dialect_impl(sqlalchemy.JSON()).process_bind_param(metadata, None)
                
                # Prepare the SQL statement
                insert_stmt = sqlalchemy.text(f"""
                INSERT INTO {self.table_name} 
                (id, filename, upload_time, embedding, product_description, product_reviews, metadata)
                VALUES (:id, :filename, :upload_time, :embedding::vector, :product_description, :product_reviews, :metadata::jsonb)
                ON CONFLICT (id) DO UPDATE
                SET filename = EXCLUDED.filename,
                    upload_time = EXCLUDED.upload_time,
                    embedding = EXCLUDED.embedding,
                    product_description = EXCLUDED.product_description,
                    product_reviews = EXCLUDED.product_reviews,
                    metadata = EXCLUDED.metadata;
                """)
                
                # Execute the statement
                conn.execute(insert_stmt, {
                    "id": id,
                    "filename": filename,
                    "upload_time": upload_time,
                    "embedding": str(vector.tolist()),  # Convert to string for pg8000
                    "product_description": product_description,
                    "product_reviews": product_reviews,
                    "metadata": metadata_json
                })
                
                # Commit the transaction
                conn.commit()
                logger.info(f"Successfully stored embedding for {id} ({filename})")
        except Exception as e:
            logger.error(f"Error storing embedding in AlloyDB: {e}")
            raise
    
    def search_similar(self, vector: np.ndarray, limit: int = 5) -> List[Any]:
        """
        Search for similar vectors in AlloyDB using pgvector cosine similarity
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
                # Check if we have data
                result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {self.table_name}"))
                count = result.scalar()
                logger.info(f"Found {count} rows in AlloyDB database")
                
                # Exit early if no data
                if count == 0:
                    logger.warning("No data in database - search will return empty results")
                    return []
                
                # Prepare and execute the search query
                query = sqlalchemy.text(f"""
                SELECT id, filename, upload_time, metadata, product_description, product_reviews,
                       1 - (embedding <=> :search_vector::vector) as similarity_score
                FROM {self.table_name}
                ORDER BY embedding <=> :search_vector::vector
                LIMIT :limit;
                """)
                
                # Execute with vector list
                vector_str = str(vector.tolist())
                result = conn.execute(query, {"search_vector": vector_str, "limit": limit})
                
                # Get and process results
                rows = result.fetchall()
                logger.info(f"Search returned {len(rows)} rows with {limit} requested")
                
                # Log the first result details
                if rows:
                    logger.info(f"Top result: id={rows[0][0]}, score={rows[0][6]}")
                
                # Process results
                search_results = []
                for row in rows:
                    # Extract values from row (order based on SELECT statement)
                    id_val = row[0]
                    filename = row[1]
                    upload_time = row[2]
                    metadata_json = row[3]
                    product_description = row[4]
                    product_reviews = row[5]
                    similarity = float(row[6])
                    
                    if similarity <= 0:
                        logger.warning(f"Unusually low similarity score: {similarity}")
                    
                    # Build payload
                    payload = {
                        "filename": filename,
                        "upload_time": upload_time.timestamp() if upload_time else None,
                        "product_description": product_description,
                        "product_reviews": product_reviews
                    }
                    
                    # Add metadata if available
                    if metadata_json:
                        payload.update(metadata_json)
                    
                    result = AlloyDBSearchResult(
                        id=id_val,
                        score=similarity,
                        payload=payload
                    )
                    search_results.append(result)
                
                return search_results
        except Exception as e:
            logger.error(f"Error searching in AlloyDB: {e}")
            raise
    
    def bulk_store_embeddings(self, embeddings_data: List[Dict]):
        """
        Store multiple embeddings in the AlloyDB database efficiently
        
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
        logger.info(f"Starting bulk storage of {len(embeddings_data)} embeddings in AlloyDB")
        
        try:
            with self.get_connection() as conn:
                # Process embeddings in batches
                batch_size = 100
                for i in range(0, len(embeddings_data), batch_size):
                    batch = embeddings_data[i:i + batch_size]
                    
                    # Create a batch insert query
                    stmt = sqlalchemy.text(f"""
                    INSERT INTO {self.table_name} 
                    (id, filename, upload_time, embedding, product_description, product_reviews, metadata)
                    VALUES (:id, :filename, :upload_time, :embedding::vector, :product_description, :product_reviews, :metadata::jsonb)
                    ON CONFLICT (id) DO UPDATE
                    SET filename = EXCLUDED.filename,
                        upload_time = EXCLUDED.upload_time,
                        embedding = EXCLUDED.embedding,
                        product_description = EXCLUDED.product_description,
                        product_reviews = EXCLUDED.product_reviews,
                        metadata = EXCLUDED.metadata;
                    """)
                    
                    # Prepare batch parameters
                    params_list = []
                    for item in batch:
                        image_id = item['id']
                        vector = item['vector']
                        metadata = item.get('metadata', {})
                        
                        # Extract common metadata fields
                        filename = metadata.pop("filename", "") if metadata else ""
                        product_description = metadata.pop("product_description", "") if metadata else ""
                        product_reviews = metadata.pop("product_reviews", "") if metadata else ""
                        upload_time = metadata.pop("upload_time", time.time()) if metadata else time.time()
                        
                        # Convert timestamp to datetime
                        if isinstance(upload_time, (int, float)):
                            from datetime import datetime
                            upload_time = datetime.fromtimestamp(upload_time)
                        
                        # Always normalize the vector
                        vector_norm = np.linalg.norm(vector)
                        if vector_norm > 0:
                            vector = vector / vector_norm
                        
                        # Convert metadata to JSON
                        metadata_json = sqlalchemy.JSON.dialect_impl(sqlalchemy.JSON()).process_bind_param(metadata, None)
                        
                        params_list.append({
                            "id": image_id,
                            "filename": filename,
                            "upload_time": upload_time,
                            "embedding": str(vector.tolist()),
                            "product_description": product_description,
                            "product_reviews": product_reviews,
                            "metadata": metadata_json
                        })
                    
                    # Execute batch
                    conn.execute(stmt, params_list)
                    conn.commit()
                    
                    logger.info(f"Processed batch of {len(batch)} embeddings")
                
                logger.info(f"Bulk storage in AlloyDB completed in {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error during bulk storage in AlloyDB: {e}")
            raise
    
    def get_metadata_by_id(self, id: str) -> Dict[str, Any]:
        """Get metadata for a specific embedding by ID"""
        try:
            with self.get_connection() as conn:
                stmt = sqlalchemy.text(
                    f"SELECT filename, product_description, product_reviews, metadata FROM {self.table_name} WHERE id = :id"
                )
                result = conn.execute(stmt, {"id": id})
                row = result.fetchone()
                
                if row:
                    result = {
                        "filename": row[0],
                        "product_description": row[1],
                        "product_reviews": row[2]
                    }
                    # Add metadata fields if available
                    if row[3]:
                        result.update(row[3])
                    return result
                raise ValueError(f"No metadata found for ID {id}")
        except Exception as e:
            logger.error(f"Error getting metadata from AlloyDB: {e}")
            raise

    def get_embedding_by_id(self, id: str) -> Optional[np.ndarray]:
        """Get a specific embedding by ID for debugging"""
        try:
            with self.get_connection() as conn:
                stmt = sqlalchemy.text(
                    f"SELECT embedding FROM {self.table_name} WHERE id = :id"
                )
                result = conn.execute(stmt, {"id": id})
                row = result.fetchone()
                
                if row:
                    # Convert from database array format to numpy
                    # Note: AlloyDB connector with pg8000 might return it in a different format
                    embedding_str = row[0]
                    if isinstance(embedding_str, str):
                        # If it's a string representation of a list
                        import ast
                        return np.array(ast.literal_eval(embedding_str))
                    else:
                        # If it's already a list/array
                        return np.array(embedding_str)
                return None
        except Exception as e:
            logger.error(f"Error getting embedding by ID {id} from AlloyDB: {e}")
            return None
    
    def get_name(self) -> str:
        """Get the name of this vector DB implementation"""
        return "alloydb"

    def __del__(self):
        """Clean up resources when the service is destroyed"""
        if hasattr(self, 'connector') and self.connector:
            self.connector.close()
            logger.info("Closed AlloyDB connector")

# Create a global instance
alloydb_service = AlloyDBVectorService()
