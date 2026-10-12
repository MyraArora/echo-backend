
import os
import json
import subprocess

from fastapi import FastAPI, HTTPException, BackgroundTasks
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel
from typing import Optional

# Import complete pipeline suite
from app.pipeline.audio_fetcher import download_audio_from_gcs
from app.pipeline.transcription import transcribe_audio_file
from app.pipeline.acoustic import extract_acoustic_features
from app.pipeline.syntax_lexical import extract_lexical_syntactic_features
from app.pipeline.narrative import extract_narrative_features


# 1. Initialize Firebase Admin SDK
if not firebase_admin._apps:
    firebase_creds_env = os.getenv("FIREBASE_CREDENTIALS")

    if firebase_creds_env:
        try:
            cred_dict = json.loads(firebase_creds_env)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("[Firebase] Initialized via FIREBASE_CREDENTIALS env var.")
        except Exception as e:
            print(f"[Firebase] Error parsing environment variable: {e}")
            raise

    elif os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        print("[Firebase] Initialized via local serviceAccountKey.json.")

    else:
        raise RuntimeError("No Firebase credentials found!")


db = firestore.client()
app = FastAPI(title="Echo Cognitive Monitoring Pipeline")


class ProcessSessionRequest(BaseModel):
    user_id: str
    session_id: str
    bucket_name: str = "echo-c1d62.firebasestorage.app"
    gcs_audio_path: str
    transcript: Optional[str] = None


def run_pipeline_task(
    user_id: str,
    session_id: str,
    bucket_name: str,
    gcs_audio_path: str,
    transcript: Optional[str],
):
    """Download, convert, analyze, and save one Echo session."""

    session_ref = (
        db.collection("users")
        .document(user_id)
        .collection("sessions")
        .document(session_id)
    )

    local_audio_path = None
    normalized_path = None

    try:
        session_ref.update({
            "status": "PROCESSING",
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        # Step 1: Download the original recording from Firebase Storage.
        local_audio_path = download_audio_from_gcs(
            bucket_name,
            gcs_audio_path,
        )

        print(
            f"[AudioPipeline] Downloaded audio for session {session_id}: "
            f"{local_audio_path} "
            f"({os.path.getsize(local_audio_path)} bytes)"
        )

        # Step 2: Convert the original audio into a standard WAV file.
        # FFmpeg handles the input container/codec, including AAC in M4A/MP4.
        normalized_path = f"/tmp/echo_{session_id}_normalized.wav"

        print(
            f"[AudioPipeline] Converting session {session_id} "
            "to mono, 16 kHz PCM WAV..."
        )

        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", local_audio_path,
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-c:a", "pcm_s16le",
                normalized_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            error_details = (
                result.stderr.strip()
                or "FFmpeg did not provide an error message."
            )
            raise RuntimeError(
                f"FFmpeg audio conversion failed: {error_details[-3000:]}"
            )

        if (
            not os.path.exists(normalized_path)
            or os.path.getsize(normalized_path) <= 44
        ):
            raise RuntimeError(
                "FFmpeg did not produce a valid, non-empty WAV file."
            )

        print(
            f"[AudioPipeline] Conversion successful: {normalized_path} "
            f"({os.path.getsize(normalized_path)} bytes)"
        )

        # All subsequent audio processing must use the converted WAV.
        audio_for_processing = normalized_path

        # Step 3: Transcribe if the Android app did not supply a transcript.
        if not transcript or not transcript.strip():
            print(
                f"[Pipeline] Auto-transcribing session {session_id}..."
            )
            transcript = transcribe_audio_file(audio_for_processing)

        if not transcript or not transcript.strip():
            raise RuntimeError(
                "Transcription returned an empty transcript."
            )

        # Step 4: Run Engine A (acoustic / prosodic features).
        acoustic_metrics = extract_acoustic_features(
            audio_for_processing
        )

        # Step 5: Run Engine B (lexical / syntactic features).
        lexical_metrics = extract_lexical_syntactic_features(
            transcript
        )

        # Step 6: Run Engine C (narrative / discourse features).
        narrative_metrics = extract_narrative_features(
            transcript
        )

        # Step 7: Save the results to Firestore.
        payload = {
            "status": "COMPLETED",
            "raw_transcript": transcript,
            "acoustic_features": acoustic_metrics,
            "lexical_syntax_features": lexical_metrics,
            "narrative_features": narrative_metrics,
            "processed_at": firestore.SERVER_TIMESTAMP,
        }

        session_ref.set(payload, merge=True)

        print(
            f"[Pipeline Success] Session {session_id} "
            "successfully processed and saved!"
        )

    except Exception as e:
        print(
            f"[Pipeline Failure] Error on session {session_id}: "
            f"{type(e).__name__}: {e}"
        )

        try:
            session_ref.update({
                "status": "FAILED",
                "error_message": f"{type(e).__name__}: {e}",
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
        except Exception as firestore_error:
            print(
                f"[Firestore] Could not update failure status for "
                f"{session_id}: {firestore_error}"
            )

    finally:
        # Remove temporary files after processing.
        for temp_path in (normalized_path, local_audio_path):
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    print(
                        f"[AudioPipeline] Removed temporary file: "
                        f"{temp_path}"
                    )
                except Exception as cleanup_error:
                    print(
                        f"[AudioPipeline] Could not remove "
                        f"{temp_path}: {cleanup_error}"
                    )


@app.get("/")
def health_check():
    return {
        "status": "online",
        "message": "Echo pipeline engine is running on Render!",
    }


@app.post("/api/v1/process-session", status_code=202)
def process_session(
    payload: ProcessSessionRequest,
    background_tasks: BackgroundTasks,
):
    session_ref = (
        db.collection("users")
        .document(payload.user_id)
        .collection("sessions")
        .document(payload.session_id)
    )

    doc = session_ref.get()

    if not doc.exists:
        raise HTTPException(
            status_code=404,
            detail="Session document not found in Firestore.",
        )

    # Queue processing so the Android client gets a quick response.
    background_tasks.add_task(
        run_pipeline_task,
        payload.user_id,
        payload.session_id,
        payload.bucket_name,
        payload.gcs_audio_path,
        payload.transcript,
    )

    return {
        "message": f"Session {payload.session_id} queued for processing.",
        "status": "QUEUED",
    }
