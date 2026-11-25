"""Browser test of the RouSanGPT page (Chromium, light and dark theme).

    pip install playwright && playwright install chromium
    python tests/ui_test.py [--shots FOLDER]

It starts the app on a fresh data folder (tests/serve_for_test.py), so your own
chats and course files are never touched. ROUSANGPT_PYTHON chooses the Python that
runs the app (default: the one running this test). The tutor's answers are faked, so
no question is sent to Gemini. Exit code 0 means every check passed.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
problems = []


def check(what, ok):
    print(("PASS  " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        problems.append(what)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def status_code(url, headers=None):
    # no proxy: the request must go straight to the app
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, headers=headers or {}), timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# Start dragging files over an element (dragenter + dragover). Returns the DataTransfer.
DRAG_JS = """([selector, files]) => {
  const dt = new DataTransfer();
  for (const f of files) dt.items.add(new File([f.body], f.name, { type: f.type }));
  const target = document.querySelector(selector);
  for (const type of ["dragenter", "dragover"])
    target.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
  return dt;
}"""
EVENT_JS = """([selector, type, dt]) => document.querySelector(selector).dispatchEvent(
  new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }))"""
ALL_FINISHED = """() => [...document.querySelectorAll('.uploads .state')]
  .every(s => s.classList.contains('ok') || s.classList.contains('err'))"""


def drag(page, selector, files):
    return page.evaluate_handle(DRAG_JS, [selector, files])


def fire(page, selector, kind, dt):
    page.evaluate(EVENT_JS, [selector, kind, dt])


def text_file(name, text):
    return {"name": name, "type": "text/plain", "body": text}


def run_checks(base, shots, work):
    # ---- the server answers only this computer's own page ----
    host = base.split("//")[1]
    check("a request from the app's own page works", status_code(base + "/api/chats", {"Origin": base}) == 200)
    check("a request from another web site is refused",
          status_code(base + "/api/chats", {"Origin": "http://evil.example"}) == 403)
    check("a request with another site's name (DNS rebinding) is refused",
          status_code(base + "/api/chats", {"Host": "evil.example:" + host.split(":")[1]}) == 403)

    picked = work / "picked-notes.txt"
    picked.write_text("Lecture 7 recording: https://example.com/lec7\nSlow start doubles the window.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            def shot(name):
                if shots:
                    page.screenshot(path=shots / f"{theme}-{name}.png")

            ctx = browser.new_context(viewport={"width": 1220, "height": 840}, color_scheme=theme)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and "404" not in m.text and errors.append(m.text))
            page.on("dialog", lambda d: d.accept())
            page.goto(base + "/")
            page.wait_for_selector("#list .item")
            shot("1-start")

            # ---- chats ----
            page.locator("#list .item", has_text="Long chat").click()
            page.wait_for_timeout(500)
            gap = page.evaluate("() => { const c = document.getElementById('chat'); "
                                "return c.scrollHeight - c.scrollTop - c.clientHeight; }")
            check(f"[{theme}] an opened chat shows its end (gap {gap:.0f}px)", gap < 5)
            shot("2-chat")
            page.locator("#list .item", has_text="deleted video").click()
            page.wait_for_selector("text=This video is no longer available", timeout=5000)
            check(f"[{theme}] a deleted video shows a note, not a broken player",
                  page.locator("#chat video").count() == 0)
            shot("3-missing-video")

            # ---- dragging files over the window ----
            dt = drag(page, "#chat", [text_file("x.txt", "x")])
            page.wait_for_timeout(150)
            check(f"[{theme}] dragging files over the window shows the drop overlay",
                  page.locator("#dropOverlay").is_visible())
            shot("4-overlay")
            fire(page, "#chat", "dragleave", dt)
            page.wait_for_timeout(100)
            check(f"[{theme}] the overlay goes away when the drag leaves", not page.locator("#dropOverlay").is_visible())

            # ---- dropping files: Materials opens and adds them ----
            dropped = f"dropped-{theme}.txt"
            dt = drag(page, "#chat", [text_file(dropped, "DHCP gives hosts an IP address.\nDORA: discover offer request ack.\n"),
                                      {"name": "photo.jpg", "type": "image/jpeg", "body": "x"}])
            fire(page, "#chat", "drop", dt)
            page.wait_for_timeout(200)
            check(f"[{theme}] dropping files opens Course materials", page.locator("#mtitle").inner_text() == "Course materials")
            check(f"[{theme}] the overlay is gone after the drop", not page.locator("#dropOverlay").is_visible())
            shot("5-adding")
            page.wait_for_function(ALL_FINISHED, timeout=180000)   # the first file also loads the search model
            rows = page.locator(".uploads .row").all_inner_texts()
            check(f"[{theme}] the dropped .txt file was added {rows}", any(dropped in r and "piece" in r for r in rows))
            check(f"[{theme}] the .jpg file was skipped with a reason", any("photo.jpg" in r and "skipped" in r for r in rows))
            listed = page.locator("#mbody > .card:nth-child(2) .row .grow", has_text=dropped)
            listed.first.wait_for(timeout=5000)
            check(f"[{theme}] the list of files shows the new file", listed.count() == 1)
            shot("6-added")

            # over the open panel, the panel's own drop zone lights up instead of the overlay
            dt = drag(page, ".drop", [text_file("x.txt", "x")])
            page.wait_for_timeout(100)
            check(f"[{theme}] the drop zone lights up over the open panel", "over" in page.locator(".drop").get_attribute("class"))
            check(f"[{theme}] no overlay over the open panel", not page.locator("#dropOverlay").is_visible())
            shot("7-dropzone")
            fire(page, ".drop", "dragleave", dt)

            # ---- choose files ----
            page.locator("#mbody input[type=file]").set_input_files(str(picked))
            page.wait_for_function(ALL_FINISHED + " && document.querySelector('.uploads .state.ok') !== null", timeout=60000)
            check(f"[{theme}] choose files adds the file", "piece" in page.locator(".uploads .row").first.inner_text())

            # ---- remove ----
            page.locator("#mbody > .card:nth-child(2) .row", has=page.locator(".grow", has_text=dropped)).locator("button").click()
            page.wait_for_timeout(800)
            check(f"[{theme}] Remove takes the file out of the list", listed.count() == 0)

            # ---- closing the panel while a file is added ----
            page.keyboard.press("Escape")
            dt = drag(page, "#chat", [text_file(f"late-{theme}.txt", "ICMP is used by ping.\n" * 50)])
            fire(page, "#chat", "drop", dt)
            page.wait_for_timeout(100)
            page.keyboard.press("Escape")
            page.wait_for_function("() => document.getElementById('status').textContent.indexOf('Course files added') !== -1",
                                   timeout=60000)
            check(f"[{theme}] the panel stays closed while the file is added", page.locator("#modal").is_hidden())
            check(f"[{theme}] the line above the message box says the file was added",
                  "Course files added" in page.locator("#status").inner_text())
            shot("8-status")

            # ---- a narrow (phone) window ----
            page.set_viewport_size({"width": 400, "height": 760})
            page.evaluate("openMaterials()")
            page.wait_for_selector("#mbody > .card:nth-child(2) .row")
            widths = page.evaluate("() => [...document.querySelectorAll('#mbody > .card:nth-child(2) .row .grow')]"
                                   ".map(e => e.getBoundingClientRect().width)")
            check(f"[{theme}] file names use the full width on a narrow window", min(widths) > 250)
            shot("9-narrow")
            page.keyboard.press("Escape")
            page.set_viewport_size({"width": 1220, "height": 840})

            # ---- the answer appears as soon as it is ready (faked: ready after 1.2 s) ----
            page.route("**/api/chat", lambda r: r.fulfill(json={"job_id": "fake"}))

            def answer(route):
                time.sleep(1.2)
                route.fulfill(json={"status": "done", "reply": "**Fake answer**: TCP is reliable.",
                                    "tools": [], "sources": [], "media": [], "model": "test", "title": "Fake"})
            page.route("**/api/result/fake*", answer)
            page.evaluate("newChat()")
            started = time.time()
            page.fill("#input", "a question")
            page.keyboard.press("Enter")
            page.wait_for_selector("text=Fake answer", timeout=10000)
            took = time.time() - started
            check(f"[{theme}] the answer shows as soon as it is ready ({took:.2f} s for a 1.2 s answer)", took < 1.9)
            shot("10-answer")

            check(f"[{theme}] no errors on the page {errors}", not errors)
            ctx.close()
        browser.close()


def main():
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1])
        shots.mkdir(parents=True, exist_ok=True)
    python = os.environ.get("ROUSANGPT_PYTHON") or sys.executable
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        log = open(work / "server.log", "w+")
        server = subprocess.Popen([python, str(HERE / "serve_for_test.py"), str(work / "data"), str(port)],
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(240):
                if server.poll() is not None:
                    break
                try:
                    if status_code(base + "/api/status") == 200:
                        break
                except OSError:
                    time.sleep(0.5)
            else:
                pass
            if server.poll() is not None or status_code(base + "/api/status") != 200:
                log.seek(0)
                print("The app did not start:\n" + log.read())
                sys.exit(1)
            run_checks(base, shots, work)
        except Exception as e:
            problems.append(f"the test stopped: {e!r}")
            print(f"FAIL  the test stopped: {e!r}")
            log.seek(0)
            print("---- app log ----\n" + log.read()[-3000:])
        finally:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()
            log.close()
    print("\nproblems:", json.dumps(problems, indent=2) if problems else "none")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
