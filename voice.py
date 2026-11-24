import io
import wave

from google.genai import types

import gemini_client

client = gemini_client.LazyClient(timeout_ms=60000)   # uses the key from Settings or .env
MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]
SAMPLE_RATE = 16000


def record_until_enter() -> bytes:
    """Record from the microphone until the user presses Enter. Returns WAV bytes."""
    import numpy as np
    import sounddevice as sd       # only needed here (the terminal app), not by the web app
    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        callback=callback):
        input("  Recording... speak now, then press Enter to stop. ")

    if not chunks:
        return b""
    audio = np.concatenate(chunks)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)        # 16-bit sound
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())
    return buffer.getvalue()


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav", language: str = "auto") -> str:
    """Turn spoken audio into text. language: 'auto', 'english' or 'arabic'.
    Returns '' on failure."""
    if not audio_bytes:
        return ""
    if language == "english":
        rule = "The speaker is speaking English. Write the transcript in English."
    elif language == "arabic":
        rule = ("The speaker is speaking Arabic (Jordanian dialect). Write the transcript in "
                "Arabic letters, but write English technical terms such as TCP, UDP, IP, DNS "
                "and router in English letters.")
    else:
        rule = ("Detect the language that is spoken (English or Arabic). If it is English, "
                "write the transcript in English letters only and never in Arabic letters. "
                "If it is Arabic, write it in Arabic letters but keep English technical terms "
                "such as TCP, UDP, IP and DNS in English letters.")
    prompt = ("Transcribe this audio exactly as spoken. " + rule +
              " Output only the transcript, nothing else. "
              "If you hear no speech, output exactly: [no speech]")
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt, types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)],
            )
            return (response.text or "").strip()
        except Exception as e:
            print(f"  ({model} failed: {str(e)[:70]})")
    return ""


# Quick self-test: run `python voice.py`
if __name__ == "__main__":
    print("Voice test. Press Enter to start recording.")
    input()
    text = transcribe(record_until_enter())
    print("I heard:", text)