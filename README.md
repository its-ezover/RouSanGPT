# RouSanGPT - Computer Networks AI Teaching Assistant

Course project for **NES 312 Computer Networks** (Instructor: Dr. Rousan).
Author: AbdulAzez Sawalma

Net.ai is an AI teaching assistant that answers from the course materials,
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
The assistant currently runs as a **terminal application on PC**.
The desktop and mobile app interfaces are [in progress / describe their status].

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
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
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
Start the assistant:
```
python chat.py
```

## How to use it
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
| `chat.py` | main assistant (chat, search, tools, voice command) |
| `ingest.py` | reads the course materials into the local search database |
| `tools.py`, `more_tools.py`, `extra_tools.py` | exact networking calculators |
| `diagram_tools.py` | diagram drawing tools |
| `quiz.py` | quiz generator and answer checker |
| `voice.py` | microphone recording and speech-to-text |
| `video_tools.py` | narrated video generator |
| `animation_tools.py` | animation engine |

## Sample outputs
See the `samples/` folder: [list your sample videos, screenshots and quiz files here].

## Known limitations
- Videos are generated in English.
- AI, voice and text-to-speech need internet. The free Gemini tier can be slow or
  busy at times; the assistant switches models automatically.
- The program opens images and videos with `xdg-open` (Linux). On other systems the
  files are still saved in their folders but may not open automatically.
- Homework detection relies on the homework files and on what the student says, so
  it reduces cheating but cannot prevent it completely.

## Copyright
The course materials are not part of this repository. [Add the signed copyright-free
agreement information here.]
