import os
from google import genai
from google.genai import types

def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribes a local audio file using Gemini's multimodal audio capabilities.
    Returns verbatim transcript string.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[TranscriptionEngine] Warning: GEMINI_API_KEY missing.")
        return ""

    client = genai.Client(api_key=api_key)

    try:
        # 1. Upload temporary audio file to Gemini Files API
        print(f"[TranscriptionEngine] Uploading {audio_path} to Gemini...")
        audio_file = client.files.upload(file=audio_path)

        prompt = (
            "Provide an accurate, verbatim transcription of this audio recording. "
            "Include all speech, hesitation markers, filler words (such as 'uh', 'um', 'like', 'you know'), "
            "and repetitions exactly as spoken. Do not paraphrase or clean up the grammar."
        )

        # 2. Transcribe using gemini-2.0-flash
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[audio_file, prompt]
        )

        # 3. Clean up the uploaded file from Gemini storage
        try:
            client.files.delete(name=audio_file.name)
        except Exception as delete_err:
            print(f"[TranscriptionEngine] Non-critical file cleanup warning: {delete_err}")

        transcript_text = response.text.strip() if response.text else ""
        print(f"[TranscriptionEngine] Transcription complete ({len(transcript_text)} characters).")
        return transcript_text

    except Exception as e:
        print(f"[TranscriptionEngine] Error transcribing audio: {e}")
        return ""
