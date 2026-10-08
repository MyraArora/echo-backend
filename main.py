import os
import json
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
            raise e
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
    bucket_name: str = "echo-audio-bucket"
    gcs_audio_path: str
    transcript: Optional[str] = None  # Auto-generated if omitted

def run_pipeline_task(user_id: str, session_id: str, bucket_name: str, gcs_audio_path: str, transcript: Optional[str]):
    """Automated background execution pipeline connecting Fetcher -> STT -> Engines A, B, C -> Firestore"""
    session_ref = db.collection("users").document(user_id).collection("sessions").document(session_id)
    
    try:
        session_ref.update({
            "status": "PROCESSING",
            "updated_at": firestore.SERVER_TIMESTAMP
        })

        # Step 1: Download audio file locally
        local_audio_path = download_audio_from_gcs(bucket_name, gcs_audio_path)

        # Step 2: Auto-transcribe if transcript was not pre-supplied
        if not transcript or not transcript.strip():
            print(f"[Pipeline] Auto-transcribing audio for session {session_id}...")
            transcript = transcribe_audio_file(local_audio_path)

        # Step 3: Run Engine A (Acoustic / Prosodic Features from Audio)
        acoustic_metrics = extract_acoustic_features(local_audio_path)

        # Clean up local audio temp file
        if os.path.exists(local_audio_path):
            os.remove(local_audio_path)

        # Step 4: Run Engine B (Lexical / Syntactic Features from Transcript)
        lexical_metrics = extract_lexical_syntactic_features(transcript)

        # Step 5: Run Engine C (Narrative / Discourse Features via Gemini)
        narrative_metrics = extract_narrative_features(transcript)

        # Step 6: Consolidate & write to Firestore
        payload = {
            "status": "COMPLETED",
            "raw_transcript": transcript,
            "acoustic_features": acoustic_metrics,
            "lexical_syntax_features": lexical_metrics,
            "narrative_features": narrative_metrics,
            "processed_at": firestore.SERVER_TIMESTAMP
        }

        session_ref.set(payload, merge=True)
        print(f"[Pipeline Success] Session {session_id} successfully processed and saved!")

    except Exception as e:
        print(f"[Pipeline Failure] Error on session {session_id}: {e}")
        session_ref.update({
            "status": "FAILED",
            "error_message": str(e),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

@app.get("/")
def health_check():
    return {"status": "online", "message": "Echo pipeline engine running on Render!"}

@app.post("/api/v1/process-session", status_code=202)
def process_session(payload: ProcessSessionRequest, background_tasks: BackgroundTasks):
    session_ref = db.collection("users").document(payload.user_id).collection("sessions").document(payload.session_id)
    doc = session_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session document not found in Firestore.")

    # Queue execution to return instantaneous HTTP 202 status to Android client
    background_tasks.add_task(
        run_pipeline_task,
        payload.user_id,
        payload.session_id,
        payload.bucket_name,
        payload.gcs_audio_path,
        payload.transcript
    )

    return {
        "message": f"Session {payload.session_id} queued for processing.",
        "status": "QUEUED"
    }
