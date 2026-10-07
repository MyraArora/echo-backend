import os
import tempfile
import json
from google.cloud import storage

def download_audio_from_gcs(bucket_name: str, gcs_blob_path: str) -> str:
    """
    Downloads an audio file from GCS to a temporary local file.
    Returns the path to the downloaded local temporary file.
    """
    # 1. Initialize Storage Client using environment variable or default credentials
    creds_json = os.getenv("FIREBASE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
        storage_client = storage.Client.from_service_account_info(creds_dict)
    else:
        storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(gcs_blob_path)

    # 2. Save to a temporary file
    temp_dir = tempfile.gettempdir()
    local_file_path = os.path.join(temp_dir, os.path.basename(gcs_blob_path))
    
    blob.download_to_filename(local_file_path)
    print(f"[AudioFetcher] Successfully downloaded gs://{bucket_name}/{gcs_blob_path} to {local_file_path}")
    
    return local_file_path
