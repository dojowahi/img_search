import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Connection parameters
params = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', 5432),
    'dbname': os.environ.get('DB_NAME', 'embeddings'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

print(f"Attempting to connect to PostgreSQL at {params['host']}:{params['port']}")
print(f"Database: {params['dbname']}, User: {params['user']}")

try:
    # Connect to PostgreSQL
    conn = psycopg2.connect(**params)
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Execute a simple query
    cursor.execute("SELECT version();")
    
    # Fetch the result
    version = cursor.fetchone()
    print(f"Connection successful! PostgreSQL version: {version[0]}")
    
    # Close cursor and connection
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Connection failed: {str(e)}")
    print("\nTroubleshooting tips:")
    print("1. Make sure PostgreSQL is running: 'sudo service postgresql status'")
    print("2. Check if port 5432 is open: 'sudo lsof -i :5432'")
    print("3. Verify your PostgreSQL credentials in .env file")
    print("4. Try connecting with psql: 'psql -h localhost -U postgres -d embeddings'")