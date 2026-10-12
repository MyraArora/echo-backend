
import os
import tempfile
import json

from google.cloud import storage


def download_audio_from_gcs(
    bucket_name: str,
    gcs_blob_path: str,
) -> str:
    """
    Download an audio file from Google Cloud Storage to a unique
    temporary local file. Return the local file path.
    """

    # Initialize the Google Cloud Storage client.
    creds_json = os.getenv("FIREBASE_CREDENTIALS")

    if creds_json:
        creds_dict = json.loads(creds_json)
        storage_client = storage.Client.from_service_account_info(
            creds_dict
        )
    else:
        storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(gcs_blob_path)

    # Preserve the original extension, e.g. .m4a or .wav.
    original_filename = os.path.basename(gcs_blob_path)
    _, extension = os.path.splitext(original_filename)

    # Create a unique temporary file so sessions cannot overwrite
    # each other's downloaded recordings.
    temp_file = tempfile.NamedTemporaryFile(
        prefix="echo_audio_",
        suffix=extension or ".audio",
        dir=tempfile.gettempdir(),
        delete=False,
    )
    local_file_path = temp_file.name
    temp_file.close()

    try:
        blob.download_to_filename(local_file_path)

        size = os.path.getsize(local_file_path)

        with open(local_file_path, "rb") as audio_file:
            header = audio_file.read(32)

        print(
            f"[AudioFetcher] Downloaded "
            f"gs://{bucket_name}/{gcs_blob_path} "
            f"to {local_file_path}"
        )
        print(
            f"[AudioFetcher] size={size} bytes, "
            f"content_type={blob.content_type!r}, "
            f"header_hex={header.hex()}, "
            f"header_repr={header!r}"
        )

        if size == 0:
            raise RuntimeError(
                f"Downloaded audio file is empty: {gcs_blob_path}"
            )

        return local_file_path

    except Exception:
        # Avoid leaving a partial file behind if downloading fails.
        if os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except OSError:
                pass

        raise
