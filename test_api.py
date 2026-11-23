import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP error", e.code, e.read().decode()[:300])
        raise


chat_id = call("POST", "/api/chats")["id"]
print("1. chat created:", chat_id)

job = call("POST", "/api/chat",
           {"chat_id": chat_id, "message": "Say hello in one short sentence."})["job_id"]
print("2. question sent, waiting for the answer...")

for i in range(60):
    time.sleep(2)
    data = call("GET", f"/api/result/{job}")
    print("   check", i + 1, "->", data.get("status"))
    if data.get("status") != "working":
        print("3. result:", json.dumps(data, indent=2)[:600])
        break

print("4. saved messages:", call("GET", f"/api/chats/{chat_id}"))
print("5. sidebar list:", call("GET", "/api/chats"))