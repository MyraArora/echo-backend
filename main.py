import os
from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel

# 1. Initialize Firebase Admin SDK
KEY_PATH = "serviceAccountKey.json"

if not firebase_admin._apps:
    if os.path.exists(KEY_PATH):
        # Running locally with key file
        cred = credentials.Certificate(KEY_PATH)
        firebase_admin.initialize_app(cred)
    else:
        # Running in Google Cloud Run (automatically uses default permissions)
        firebase_admin.initialize_app()

db = firestore.client()

app = FastAPI(title="Cognitive Decline Processing Engine")

class ProcessSessionRequest(BaseModel):
    user_id: str
    session_id: str

@app.get("/")
def health_check():
    return {"status": "online", "message": "Server is connected to Firestore!"}

@app.post("/api/v1/process-session", status_code=202)
def process_session(payload: ProcessSessionRequest):
    # Reference to the document in Firestore
    session_ref = db.collection("users").document(payload.user_id).collection("sessions").document(payload.session_id)
    doc = session_ref.get()

    # Check if Android app actually created this session record
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session record not found in Firestore.")

    # Update status in Firestore to PROCESSING
    session_ref.update({
        "status": "PROCESSING",
        "updated_at": firestore.SERVER_TIMESTAMP
    })

    return {
        "message": f"Successfully received session {payload.session_id}!",
        "status": "PROCESSING"
    }