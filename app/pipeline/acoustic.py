import librosa
import numpy as np

def extract_acoustic_features(audio_path: str) -> dict:
    """
    Extracts key prosodic and acoustic features from an audio file:
    - Duration (seconds)
    - Total Pause Time & Pause Ratio
    - Fundamental Frequency (Pitch) Mean & Standard Deviation
    - Speech Tempo / Energy Dynamics
    """
    # 1. Load audio file with librosa
    y, sr = librosa.load(audio_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)

    if duration == 0:
        return {
            "duration_sec": 0,
            "pause_time_sec": 0,
            "pause_ratio": 0,
            "mean_f0_hz": 0,
            "f0_std_hz": 0,
            "speaking_rate_ratio": 0
        }

    # 2. Detect non-silent intervals (TopDB = 20 dB threshold)
    non_silent_intervals = librosa.effects.split(y, top_db=20)
    
    total_speech_time = 0.0
    for start_sample, end_sample in non_silent_intervals:
        total_speech_time += (end_sample - start_sample) / sr
        
    pause_time = max(0.0, duration - total_speech_time)
    pause_ratio = pause_time / duration if duration > 0 else 0.0

    # 3. Extract Fundamental Frequency (Pitch / F0) using pyIN algorithm
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, 
        fmin=librosa.note_to_hz('C2'), 
        fmax=librosa.note_to_hz('C6'), 
        sr=sr
    )
    
    # Filter out unvoiced / NaN frames
    valid_f0 = f0[~np.isnan(f0)] if f0 is not None else []
    
    if len(valid_f0) > 0:
        mean_f0 = float(np.mean(valid_f0))
        std_f0 = float(np.std(valid_f0))
    else:
        mean_f0 = 0.0
        std_f0 = 0.0

    return {
        "duration_sec": round(float(duration), 2),
        "speech_time_sec": round(float(total_speech_time), 2),
        "pause_time_sec": round(float(pause_time), 2),
        "pause_ratio": round(float(pause_ratio), 4),
        "mean_pitch_f0_hz": round(mean_f0, 2),
        "pitch_variability_f0_std": round(std_f0, 2)
    }
