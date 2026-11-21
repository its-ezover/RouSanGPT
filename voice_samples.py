import subprocess
import sys
from pathlib import Path

SAMPLE = ("Hi everyone! Today we're going to look at how a TCP connection starts. "
          "Think of it like a phone call. First you say hello, then the other person "
          "answers, and only then do you start talking.")

CANDIDATES = [
    "en-US-AvaMultilingualNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-BrianMultilingualNeural",
    "en-US-AndrewNeural",
    "en-US-AvaNeural",
    "en-US-BrianNeural",
    "en-US-ChristopherNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
]

Path("voice_samples").mkdir(exist_ok=True)
for voice in CANDIDATES:
    out = Path("voice_samples") / f"{voice}.mp3"
    result = subprocess.run(
        [sys.executable, "-m", "edge_tts", "--voice", voice, "--rate=-5%",
         f"--text={SAMPLE}", "--write-media", str(out)],
        capture_output=True, text=True, timeout=90,
    )
    ok = result.returncode == 0 and out.exists()
    print("OK     " if ok else "MISSING", voice)

print("\nNow listen to the files in the voice_samples folder.")