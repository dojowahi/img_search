
-- Make sure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the image embeddings table
CREATE TABLE IF NOT EXISTS image_embeddings (
    id TEXT PRIMARY KEY,
    filename TEXT,
    upload_time TIMESTAMP,
    embedding vector(512),
    metadata JSONB
);

-- Create an index for faster vector similarity search
CREATE INDEX IF NOT EXISTS embedding_idx 
ON image_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);