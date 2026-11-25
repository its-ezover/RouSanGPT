"""Start RouSanGPT for the tests, on an empty data folder with a few chats in it.

    python tests/serve_for_test.py DATA_FOLDER PORT

Used by tests/ui_test.py; nothing here touches your real data.
"""
import os
import sys
from pathlib import Path

data, port = Path(sys.argv[1]), int(sys.argv[2])
os.environ["ROUSANGPT_DATA_DIR"] = str(data)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import history_store  # noqa: E402
import settings  # noqa: E402

history_store.init()
if not history_store.list_chats():
    # a key, so the first-run screen stays away (no question is ever sent to Gemini)
    settings.save({"gemini_api_key": "test-key-not-used"})
    long_chat = history_store.create_chat()
    for i in range(1, 13):
        history_store.add_exchange(long_chat, f"Question {i} about TCP", {
            "reply": f"Answer {i}.\n\n" + "TCP is a reliable transport protocol. " * 25,
            "model": "test"})
    history_store.rename_chat(long_chat, "Long chat")
    video_chat = history_store.create_chat()
    history_store.add_exchange(video_chat, "Make a video about DNS", {
        "reply": "Here is the video.", "model": "test",
        "media": [{"type": "video", "url": "/files/videos/deleted_video.mp4"}]})
    history_store.rename_chat(video_chat, "Chat with a deleted video")

import uvicorn  # noqa: E402

import server  # noqa: E402

uvicorn.run(server.app, host="127.0.0.1", port=port, log_level="warning")
