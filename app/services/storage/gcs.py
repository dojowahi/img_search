import logging
import os
import tempfile
import uuid
from datetime import timedelta
from typing import Optional, Tuple

from fastapi import UploadFile
from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import settings
from app.services.storage.base import StorageService

logger = logging.getLogger(__name__)

class GCSStorageService(StorageService):
    """Google Cloud Storage implementation of StorageService"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.prefix = settings.GCS_UPLOADS_PREFIX
        self.client = None
        self.bucket = None
        self.signed_url_expiration = timedelta(minutes=settings.GCS_SIGNED_URL_EXPIRATION_MINUTES)
        self.credentials = None
        self.service_account_info = settings.GCP_SERVICE_ACCOUNT_FILE
    
    async def initialize(self):
        """Initialize the GCS storage service"""
        # Create local temp directory
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Initialize GCS client with service account if available
        try:
            if self.service_account_info and self.service_account_info != "None" and os.path.exists(self.service_account_info):
                logger.info(f"Using service account key file: {self.service_account_info}")
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.service_account_info
                )
                self.client = storage.Client(
                    credentials=self.credentials,
                    project=settings.GCP_PROJECT_ID
                )
            else:
                logger.warning("No service account key file found. Using default credentials.")
                logger.info("Connected to GCS using Application Default Credentials")
                self.client = storage.Client(project=settings.GCP_PROJECT_ID)
        except Exception as e:
            logger.error(f"Error initializing GCS client: {e}")
            raise
        
        # Get bucket
        try:
            self.bucket = self.client.get_bucket(self.bucket_name)
            logger.info(f"Connected to GCS bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error connecting to GCS bucket: {e}")
            raise
    
    async def save_upload(self, file: UploadFile,suffix: Optional[str] = None) -> Tuple[str, bool]:
        """
        Save an uploaded file to temporary local storage for processing
        Returns tuple of (temp_file_path, is_cleanup_needed)
        """
        if suffix is None:
            suffix = os.path.splitext(file.filename)[1]
        temp_file = tempfile.NamedTemporaryFile(delete=False, dir=self.upload_dir,suffix=suffix)
        temp_file_name = temp_file.name
        temp_file.close()
        
        with open(temp_file_name, "wb") as f:
            f.write(await file.read())
        
        return temp_file_name, True
    
    def store_file(self, temp_file_path: str, filename: str, file_id: Optional[str] = None,gcs_folder: Optional[str] = None) -> Tuple[str, str]:
        """
        Upload a file from temporary storage to GCS
        Returns tuple of (file_id, gcs_object_path)
        """
        if file_id is None:
            file_id = str(uuid.uuid4())
        
        # Define the GCS object name
        object_name = f"{self.prefix}{file_id}_{filename}""""
    Upload a file from temporary storage to GCS.
    Returns tuple of (file_id, gcs_object_path)

    Args:
        temp_file_path (str): Path to the temporary file.
        filename (str): Name of the file.
        file_id (Optional[str], optional): Optional file ID. Defaults to a UUID.
        gcs_folder (Optional[str], optional): Optional GCS folder. Defaults to None, using self.prefix.
    """
        if file_id is None:
            file_id = str(uuid.uuid4())

        # Determine the GCS object name with optional folder
        if gcs_folder:
            object_name = f"{gcs_folder}/{file_id}_{filename}"
        else:
            object_name = f"{self.prefix}{file_id}_{filename}"

        
        # Upload file to GCS
        blob = self.bucket.blob(object_name)
        blob.upload_from_filename(temp_file_path)
        
        # Generate a signed URL with the configured expiration
        # signed_url = blob.generate_signed_url(
        #     version="v4",
        #     expiration=self.signed_url_expiration,
        #     method="GET"
        # )
        
        # Return both the file_id and the object path (not the signed URL)
        return file_id, object_name  # Store object path instead of URL
    
    def get_fresh_signed_url(self, object_name: str) -> str:
        """Generate a fresh signed URL for a GCS object"""
        blob = self.bucket.blob(object_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=self.signed_url_expiration,
            method="GET"
        )
        return url

    def get_file_path(self, file_id: str, filename: Optional[str] = None, gcs_folder: Optional[str] = None) -> Optional[str]:
        """Get the GCS URI for a stored file"""

        prefix = f"{gcs_folder}/" if gcs_folder else self.prefix

        if filename:
            return f"gs://{self.bucket_name}/{prefix}{file_id}_{filename}"
        else:
            # List blobs with the prefix to find the matching file
            blobs = list(self.client.list_blobs(
                self.bucket_name,
                prefix=f"{prefix}{file_id}_",
                max_results=1
            ))

            if blobs:
                return f"gs://{self.bucket_name}/{blobs[0].name}"

        return None
    
    def get_public_url(self, file_id: str, filename: Optional[str] = None, gcs_folder: Optional[str] = None) -> Optional[str]:
        """
        Get a URL for accessing the file
        Will try to generate a signed URL, or fall back to direct URL
        """
        prefix = f"{gcs_folder}/" if gcs_folder else self.prefix
        object_name = None

        if filename:
            object_name = f"{prefix}{file_id}_{filename}"
        else:
            # List blobs with the prefix to find the matching file
            blobs = list(self.client.list_blobs(
                self.bucket_name,
                prefix=f"{prefix}{file_id}_",
                max_results=1
            ))

            if blobs:
                object_name = blobs[0].name

        if object_name:
            blob = self.bucket.blob(object_name)
            try:
                # Try to generate a signed URL
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=self.signed_url_expiration,
                    method="GET"
                )
                return url
            except Exception as e:
                logger.warning(f"Could not generate signed URL: {e}")
                # Fall back to direct URL
                return f"gs://{self.bucket_name}/{object_name}"

        return None
    
    def find_full_bkg_img_gcs_path(self,partial_path:str) -> str:
        """
        Finds the full GCS path to sample_0.png within the given partial path.

        Args:
            partial_path (str): The partial GCS path.

        Returns:
            str: The full GCS path, or None if not found.
        """
        try:
            # Parse bucket name and directory path
            path_parts = partial_path.replace("gs://", "").split("/")
            logger.info(f"Path Parts:{path_parts}")
            bucket_name = path_parts[0]
            directory_path = "/".join(path_parts[1:])

            logger.info(f"Bucket:{bucket_name}")
            logger.info(f"Directory path:{directory_path}")
            # Initialize GCS client
            client = storage.Client()
            bucket = client.bucket(bucket_name)

            # List directories within the given path
            blobs = client.list_blobs(bucket, prefix=directory_path + "/")
            # logger.info(f"Blob length {len(blobs)}")
            directories = set()
            for blob in blobs:
                parts = blob.name.split("/")
                set_path_parts = set(path_parts)
                set_parts = set(parts)
                directories = set_parts - set_path_parts
                directories.remove("sample_0.png")
            # Iterate through directories and check for sample_0.png
            for directory in directories:
                full_directory_path = os.path.join(directory_path, directory)
                blob_path = os.path.join(full_directory_path, "sample_0.png")
                logger.info(f"Blob:{blob_path}")
                blob = bucket.blob(blob_path)
                if blob.exists():
                    signed_gcs_url = self.get_fresh_signed_url(blob_path)
                    return signed_gcs_url
                    # return f"gs://{bucket_name}/{blob_path}"

            return None  # File not found
        except Exception as e:
            print(f"Error finding file: {e}")
            return None
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """Clean up a temporary file"""
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

# Create a global instance
gcs_storage_service = GCSStorageService()
