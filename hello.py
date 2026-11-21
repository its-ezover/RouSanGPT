import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# timeout is in milliseconds: give up on a request after 30 seconds,
# and don't let the library retry silently on its own (attempts=1)
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=30000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

# Models to try, in order. If one fails, we try the next.
MODELS = ["gemini-3.8-flash", "gemini-3.1-flash-lite"]

def ask(question):
    for model in MODELS:
        for attempt in range(2):  # try each model up to 2 times
            print(f"Asking {model} (try {attempt + 1}/2)...")
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=question,
                )
                return response.text
            except Exception as e:
                print(f"  Failed: {str(e)[:150]}")
                time.sleep(3)
    return "Sorry, all models failed. Try again in a few minutes."

print(ask("Explain what an IP address is in two sentences."))