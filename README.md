# RouSanGPT - Computer Networks AI Teaching Assistant

Course project for **NES 312 Computer Networks** (Instructor: Dr. Rousan).
Author: AbdulAzez Sawalma

RouSanGPT is an AI teaching assistant that answers from the course materials,
calculates networking problems exactly, draws diagrams, runs quizzes, listens to
voice questions, and creates narrated educational videos. It is built only with
free tools.

## Features
- **Socratic tutor with course knowledge:** answers from the lecture slides, textbooks
  and homework files (retrieval-augmented generation with a local ChromaDB), and
  names the slide or page it used.
- **Exact calculators:** subnetting (CIDR), transmission/propagation delay,
  bandwidth-delay product, CRC, Internet checksum, Dijkstra's shortest paths and a
  safe general calculator, so the AI never guesses numbers.
- **Diagrams:** message-sequence diagrams (TCP handshake, DNS...), network
  topologies and packet headers (TCP, UDP, IP).
- **Quizzes:** multiple-choice, fill-in-the-blank and Wireshark-style packet
  analysis questions, built from the course materials.
- **Voice input:** speak a question in English or Arabic.
- **Educational videos:** narrated MP4 videos made of bullet slides, diagrams and
  animations (message exchange, store-and-forward packet flow, sliding window,
  Dijkstra's algorithm).
- **Academic integrity:** homework problems trigger "hint mode" (hints and similar
  practice problems instead of final answers). Answer keys and solution manuals are
  hidden from the tutor.

## Current status
RouSanGPT runs as a **Linux desktop app** (see below), as a web app in the browser
(`python server.py`) and as a terminal app (`python chat.py`).

## Linux app
### Install (one line)
```
git clone https://github.com/its-ezover/RouSanGPT.git && cd RouSanGPT && ./install.sh
```
The installer needs no `sudo`. It checks the programs RouSanGPT uses and prints the
install command (Arch, Debian/Ubuntu, Fedora) for anything missing, then installs
the app for your user and adds **RouSanGPT** to the app menu (Education).

Already used RouSanGPT from this folder? Keep your chats, course database, formula
tools and videos with:
```
./install.sh --import-data ~/path/to/RouSanGPT
```
(It also offers to copy the Gemini API key from that folder's `.env`.)

### First run
Click **RouSanGPT** in the app menu. The window opens after a few seconds. The
first time, it asks for your free Gemini API key (from
https://aistudio.google.com/apikey); it is tested and stored only on your
computer. Then add your course files (PDF, PPTX, PPT, TXT) in **Materials**.
Without course files the tutor still works and answers from general knowledge.

Clicking the icon again while the app is open just brings up another window.
Closing the window stops the app (after about 10 seconds). **Settings > Quit
RouSanGPT** stops it right away.

### Where things are
| What | Where |
|---|---|
| Your data: chats, course database, materials, videos, settings, API key | `~/.local/share/RouSanGPT/data` (or `$XDG_DATA_HOME/RouSanGPT/data`) |
| Log file | `~/.local/share/RouSanGPT/data/logs/rousangpt.log` |
| The program and its Python packages | `~/.local/share/RouSanGPT/app` and `.../venv` |
| Command and menu entry | `~/.local/bin/rousangpt`, `~/.local/share/applications/rousangpt.desktop` |

### Update and uninstall
- Update: `git pull && ./install.sh` (your data is kept).
- Uninstall: `./uninstall.sh` (your data is kept), or `./uninstall.sh --purge` to
  delete the data too (it asks first).

### Local model (optional, works offline)
Install Ollama (https://ollama.com/download, on Arch `sudo pacman -S ollama`).
In **Settings > Local model** you can see whether Ollama runs, start it, see a
model recommended for your computer's memory, download it with a progress bar and
choose it. Then pick "Local model" at the top of the chat; answers show
"Answered by: local: ...".
On Arch, the `ollama` package runs a system service that keeps its models in
`/var/lib/ollama`, while a manually started `ollama serve` uses `~/.ollama`; the
panel shows which one is in use. RouSanGPT only starts `ollama serve` if no Ollama
is answering yet.

### Troubleshooting
- **The window is a normal browser tab:** no Chromium-based browser or Firefox was
  found. Install one (`sudo pacman -S chromium`). With a Chromium-based browser
  (Chromium, Chrome, Brave, Edge, Vivaldi) RouSanGPT opens in its own app window;
  otherwise it uses Firefox with a separate, tab-less profile.
- **Microphone:** allow the microphone when the window asks. Voice input needs a
  Chromium-based browser or Firefox (it does not work in some embedded web views).
  Check that the microphone works in your system sound settings.
- **Videos, animations or voice input fail:** FFmpeg is missing
  (`sudo pacman -S ffmpeg`, `sudo apt install ffmpeg`, `sudo dnf install ffmpeg`).
- **Topology diagrams fail:** Graphviz is missing (`sudo pacman -S graphviz`,
  `sudo apt install graphviz`, `sudo dnf install graphviz`).
- **Nothing happens when clicking the icon:** look at the log file above, or run
  `~/.local/bin/rousangpt --console` in a terminal to see the messages.
- The first start downloads the search model (about 80 MB) once, so it needs the
  internet.

## Dev mode (from the repo)

## Requirements
- Python 3.10 or newer (developed with Python 3.14 on Linux, CachyOS)
- A free Gemini API key from https://aistudio.google.com
- System tools (Arch/CachyOS names; use your system's equivalents):
  ```
  sudo pacman -S ffmpeg graphviz portaudio catdoc
  ```
  Optional: `libreoffice-fresh`, only to convert old `.ppt` slides to `.pptx`.
- Internet connection (AI, voice transcription and text-to-speech use online
  services).

## Setup
```
git clone https://github.com/its-ezover/RouSanGPT.git
cd RouSanGPT
python -m venv venv
source venv/bin/activate          # fish shell: source venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env              # then open .env and paste your Gemini API key
```
Create a folder named `materials` and put your course files in it (PDF, PPTX, PPT,
TXT). The materials are not included in this repository. Then build the search
database (takes a few minutes):
```
python ingest.py
```
Start the assistant in the terminal:
```
python chat.py
```
or as a web app in your browser (http://127.0.0.1:8000):
```
python server.py
```
or as the desktop app, using this folder for data: `python launcher.py`.

## How to use it (CLI)
At the `You:` prompt:
- Type a question, for example `What is the difference between TCP and UDP?`
- `/voice` to ask with the microphone, `/paste` for a multi-line question
- `Give me a quiz on the TCP handshake with 3 questions`
- `Draw the TCP header`
- `Show me an animation of Dijkstra's algorithm on a graph with links A-B 2, A-C 5, B-C 1`
- `Make a video explaining how DNS works`
- `quit` to exit

## Project structure
| File | Purpose |
|---|---|
| `agent.py` | the tutor: search, tools, Gemini and local model |
| `chat.py` | terminal app |
| `server.py`, `web/` | web app (FastAPI) and its page |
| `launcher.py`, `install.sh`, `uninstall.sh` | Linux desktop app |
| `app_paths.py`, `settings.py`, `binaries.py`, `tts.py`, `gemini_client.py`, `local_ai.py` | data folder, settings, external programs, text-to-speech, Gemini key, Ollama |
| `history_store.py`, `formula_tools.py`, `ingest_lib.py` | saved chats, formula tools, adding course files |
| `ingest.py` | reads the course materials into the local search database |
| `tools.py`, `more_tools.py`, `extra_tools.py` | exact networking calculators |
| `diagram_tools.py` | diagram drawing tools |
| `quiz.py` | quiz generator and answer checker |
| `voice.py` | microphone recording and speech-to-text |
| `video_tools.py` | narrated video generator |
| `animation_tools.py` | animation engine |



## Known limitations
- Videos are generated in English.
- AI, voice and text-to-speech need internet. The free Gemini tier can be slow or
  busy at times; the assistant switches models automatically.
- The terminal app opens images and videos with the system's default program; the
  web and desktop app show them inside the chat.
- Homework detection relies on the homework files and on what the student says, so
  it reduces cheating but cannot prevent it completely.

