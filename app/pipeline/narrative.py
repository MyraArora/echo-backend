import os
import json
from google import genai
from google.genai import types

def extract_narrative_features(transcript: str) -> dict:
    """
    Evaluates higher-level discourse and narrative metrics using Gemini:
    - Topic Coherence Score (0-10)
    - Ambiguous Reference Count
    - Idea Repetition Score (0-10)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[NarrativeEngine] Warning: GEMINI_API_KEY environment variable not found.")
        return {
            "coherence_score": 5.0,
            "ambiguous_reference_count": 0,
            "repetition_score": 0.0,
            "narrative_notes": "Gemini API key missing; default scores applied."
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are a clinical linguistic assistant evaluating speech for cognitive monitoring.
    Analyze the following speech transcript for narrative coherence and discourse markers:

    TRANSCRIPT:
    "{transcript}"

    Provide your response strictly as a JSON object with these exact keys:
    {{
        "coherence_score": float (0.0 to 10.0, where 10 means perfectly logical and structured),
        "ambiguous_reference_count": int (count of pronouns or terms like "that thing", "she", "they" with unclear targets),
        "repetition_score": float (0.0 to 10.0, where high values mean frequent restatement of the same idea),
        "narrative_notes": string (concise 1-sentence summary of story progression)
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        result = json.loads(response.text)
        return {
            "coherence_score": float(result.get("coherence_score", 5.0)),
            "ambiguous_reference_count": int(result.get("ambiguous_reference_count", 0)),
            "repetition_score": float(result.get("repetition_score", 0.0)),
            "narrative_notes": str(result.get("narrative_notes", ""))
        }
    except Exception as e:
        print(f"[NarrativeEngine] Error during Gemini extraction: {e}")
        return {
            "coherence_score": 5.0,
            "ambiguous_reference_count": 0,
            "repetition_score": 0.0,
            "narrative_notes": f"Extraction failed: {str(e)}"
        }
