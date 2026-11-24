"""Text-to-speech with edge-tts (Python API, no extra process)."""
import asyncio
from pathlib import Path


async def _save(text, voice, rate, out_path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))


def synthesize(text, out_path, voices, rate="+0%"):
    """Write spoken `text` as an MP3 to out_path, trying the voices in order.
    Raises RuntimeError if every voice fails."""
    last_error = ""
    for voice in voices:
        try:
            asyncio.run(_save(text, voice, rate, out_path))
            if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                return voice
        except Exception as e:
            last_error = str(e)[:200]
    raise RuntimeError("Text-to-speech failed (is the internet working?) " + last_error)
