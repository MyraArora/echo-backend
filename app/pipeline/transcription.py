import os
from groq import Groq

def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribes a local audio file using Groq's Whisper API (whisper-large-v3-turbo).
    Returns verbatim transcript string.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[TranscriptionEngine] Warning: GROQ_API_KEY missing.")
        return ""

    client = Groq(api_key=api_key)

    if not os.path.exists(audio_path):
        print(f"[TranscriptionEngine] Error: Audio file not found at {audio_path}")
        return ""

    try:
        print(f"[TranscriptionEngine] Transcribing {audio_path} using Groq Whisper...")
        
        with open(audio_path, "rb") as audio_file:
            translation = client.audio.transcriptions.create(
                file=(audio_path, audio_file.read()),
                model="whisper-large-v3-turbo",
                prompt=(
                    "Provide an accurate, verbatim transcription of this audio recording. "
                    "Include all speech, hesitation markers, filler words (such as 'uh', 'um', 'like', 'you know'), "
                    "and repetitions exactly as spoken. Do not paraphrase or clean up the grammar."
                ),
                response_format="json",
                temperature=0.0
            )

        transcript_text = translation.text.strip() if hasattr(translation, "text") else ""
        print(f"[TranscriptionEngine] Transcription complete ({len(transcript_text)} characters).")
        return transcript_text

    except Exception as e:
        print(f"[TranscriptionEngine] Error transcribing audio with Groq: {e}")
        return ""
