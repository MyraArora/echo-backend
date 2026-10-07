import os
import json
from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore
from pydantic import BaseModel

# 1. Initialize Firebase Admin SDK
if not firebase_admin._apps:
    firebase_creds_env = os.getenv("FIREBASE_CREDENTIALS")
    
    if firebase_creds_env:
        # Running on Render (using environment variable)
        try:
            cred_dict = json.loads(firebase_creds_env)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("Successfully initialized Firebase via FIREBASE_CREDENTIALS env var.")
        except Exception as e:
            print(f"Error parsing FIREBASE_CREDENTIALS env var: {e}")
            raise e
    elif os.path.exists("serviceAccountKey.json"):
        # Running locally on your laptop
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        print("Successfully initialized Firebase via local serviceAccountKey.json.")
    else:
        raise RuntimeError("No Firebase credentials found! Set FIREBASE_CREDENTIALS on Render or provide serviceAccountKey.json locally.")

db = firestore.client()

app = FastAPI(title="Cognitive Decline Processing Engine")

class ProcessSessionRequest(BaseModel):
    user_id: str
    session_id: str

@app.get("/")
def health_check():
    return {"status": "online", "message": "Server is up and connected to Firestore on Render!"}

@app.post("/api/v1/process-session", status_code=202)
def process_session(payload: ProcessSessionRequest):
    session_ref = db.collection("users").document(payload.user_id).collection("sessions").document(payload.session_id)
    doc = session_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session record not found in Firestore.")

    session_ref.update({
        "status": "PROCESSING",
        "updated_at": firestore.SERVER_TIMESTAMP
    })

    return {
        "message": f"Successfully received session {payload.session_id}!",
        "status": "PROCESSING"
    }
