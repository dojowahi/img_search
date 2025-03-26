# Image Search Application

This project is a FastAPI-based image search application that uses CLIP embeddings to find similar images based on text queries or uploaded images.

## Features

*   **Image Upload:** Upload images to the application.
*   **Search by Text:** Search for images similar to a text query.
*   **Search by Image:** Search for images similar to an uploaded image.
*   **Google Cloud Storage Integration:** Stores images in Google Cloud Storage.
*   **Vector Database Support:** Supports CloudSQL for PostgreSQL for storing image embeddings.
*   **API Endpoints:** Provides a REST API for interacting with the application.

## Dependencies

*   fastapi
*   uvicorn
*   python-multipart
*   Pillow
*   torch
*   clip
*   google-cloud-storage
*   pydantic
*   numpy
*   python-dotenv
*   google-genai
*   pydantic-settings
*   psycopg2-binary

## Setup

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    cd img_search
    ```

2.  Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  Configure the application:

    *   Create a `.env` file in the `app/` directory with the following variables:

        ```
        DB_PASSWORD="your_db_password"
        GCP_SERVICE_ACCOUNT_FILE="/path/to/your/service_account.json"
        GCP_PROJECT_ID="your_gcp_project_id"
        GCP_REGION="your_gcp_region"
        ```

    *   Update the values with your actual credentials.

4.  Run the application:

    ```bash
    python run.py
    ```

## API Endpoints

### Upload Images

*   **Endpoint:** `POST /api/v1/upload_images/`
*   **Description:** Upload multiple images.
*   **Request Body:** A list of image files.
*   **Response:** A list of uploaded image IDs and their URLs.

### Search by Text

*   **Endpoint:** `GET /api/v1/search_by_text/?query=<text>&limit=<limit>`
*   **Description:** Search for images similar to a text query.
*   **Parameters:**
    *   `query`: The text query.
    *   `limit`: The maximum number of results to return (default: 5).
*   **Response:** A list of similar images, sorted by similarity score.

### Search by Image

*   **Endpoint:** `POST /api/v1/search_by_image/?limit=<limit>`
*   **Description:** Search for images similar to an uploaded image.
*   **Request Body:** An image file.
*   **Parameters:**
    *   `limit`: The maximum number of results to return (default: 5).
*   **Response:** A list of similar images, sorted by similarity score.

### Get Image

*   **Endpoint:** `GET /api/v1/get_image/<image_id>`
*   **Description:** Retrieve an image by its ID.
*   **Response:** Redirects to the image URL in Google Cloud Storage.

### Generate Tags

*   **Endpoint:** `POST /api/v1/generate_tags/<image_id>`
*   **Description:** Generate tags for an image using an LLM.
*   **Response:** HTML with the generated tags JSON.

### Health Check

*   **Endpoint:** `GET /api/v1/health`
*   **Description:** Check the service status and configuration.
*   **Response:** Service status and configuration information.

## Google Cloud Storage

The application uses Google Cloud Storage to store the uploaded images. You need to configure the following:

*   A Google Cloud Storage bucket.
*   A service account with the necessary permissions to access the bucket.
*   The `GCP_SERVICE_ACCOUNT_FILE` environment variable pointing to the service account key file.
*   The `GCP_PROJECT_ID` environment variable set to your Google Cloud project ID.
*   The `GCS_BUCKET_NAME` environment variable set to your Google Cloud Storage bucket name.

## Vector Database

*   **PostgreSQL:** A relational database with the pgvector extension for vector storage.

You can configure the vector database type using the `VECTOR_DB_TYPE` environment variable.


### PostgreSQL

To use PostgreSQL, set the `VECTOR_DB_TYPE` environment variable to `postgres` and configure the following environment variables:

*   `DB_INSTANCE_NAME`: The name of your Cloud SQL instance.
*   `DB_NAME`: The name of the database.
*   `DB_USER`: The database user.
*   `DB_PASSWORD`: The database password.
*   `DB_HOST`: The database host.
*   `DB_PORT`: The database port.
*   `INSTANCE_CONNECTION_NAME`: The Cloud SQL instance connection name.

## Cloud SQL Proxy

The application uses Cloud SQL Proxy to connect to Cloud SQL instances both locally and in the Docker image. Cloud SQL Proxy provides a secure way to connect to Cloud SQL without needing to manage complex networking configurations.

### Installing Cloud SQL Proxy Locally

You can install Cloud SQL Proxy locally using the following steps:

1.  Download the Cloud SQL Proxy binary for your operating system from the [Cloud SQL Proxy documentation](https://cloud.google.com/sql/docs/mysql/sql-proxy).
2.  Make the binary executable:

    ```bash
    chmod +x cloud-sql-proxy
    ```

3.  Start the Cloud SQL Proxy:

    ```bash
    ./cloud-sql-proxy --unix-socket=/tmp/cloudsql/<your_instance_connection_name> <your_gcp_project_id>:<your_gcp_region>:<your_instance_name>
    ```

    Replace `<your_instance_connection_name>`, `<your_gcp_project_id>`, `<your_gcp_region>`, and `<your_instance_name>` with your actual values.

## Docker

The application can be containerized using Docker. A `Dockerfile` is included in the repository.

To build the Docker image:

```bash
docker build -t img_search .
```

To run the Docker container:

```bash
docker run -p 8000:8000 img_search
```

## Bulk Upload

The application supports bulk uploading embeddings from a JSON file. This feature is only supported for PostgreSQL.

*   **Endpoint:** `POST /api/v1/bulk_upload/`
*   **Request Body:** A JSON file containing a list of image data. Each item in the list should have the following format:

    ```json
    {
        "image_path": "/path/to/image.jpg",
        "id": "image_id",
        "metadata": {
            "key": "value"
        }
    }
    ```

## High-Level Flow

The application consists of the following main components:

*   `app/main.py`: The main application entry point.
*   `app/api/routes/image_routes.py`: Handles image-related API requests.
*   `app/api/routes/search_routes.py`: Handles search-related API requests.
*   `app/core/config.py`: Contains application configuration.
*   `app/services/storage/gcs.py`: Handles interactions with Google Cloud Storage.
*   `app/services/embedding.py`: Creates image embeddings.
*   `app/services/llm_service.py`: Interacts with a Large Language Model.
*   `app/services/vector_db/postgres.py`: Handles interactions with the vector database.

**Image Upload Process:**

1.  The process starts with a request to the `/upload_images/` API endpoint.
2.  The system validates if the uploaded file is an image.
3.  If the file is an image, the system saves the uploaded file temporarily.
4.  The system creates an image embedding using the embedding service.
5.  A unique ID is generated for the image.
6.  The image is stored in Google Cloud Storage (GCS).
7.  The embedding and metadata are stored in the vector database.
8.  The system returns the uploaded image IDs and URLs.
9.  If the file is not an image, the file is skipped.

**Search Process:**

1.  The process starts with a request to the `/search_by_text/` or `/search_by_image/` API endpoint.
2.  The system creates an embedding for the search query (either text or image).
3.  The embedding is normalized.
4.  The system searches for similar images in the vector database using the embedding.
5.  The image metadata is retrieved from the vector database.
6.  A signed URL is generated from Google Cloud Storage (GCS) for each image.
7.  The search results are prepared.
8.  The system returns the search results.

## Contributing

Contributions are welcome! Please submit a pull request with your changes.
