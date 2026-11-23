import agent


def read_question():
    """Read what the student types. /paste for multi-line text, /voice for the microphone."""
    first = input("You: ")
    if first.strip().lower() == "/paste":
        print("Paste your text now, then type /end on a new line and press Enter.")
        lines = []
        while True:
            line = input()
            if line.strip().lower() == "/end":
                break
            lines.append(line)
        return "\n".join(lines)
    if first.strip().lower() == "/voice":
        from voice import record_until_enter, transcribe
        text = transcribe(record_until_enter())
        print("  You said:", text)
        if not text or text == "[no speech]":
            return ""
        return text
    return first


print(f"Slides: {len(agent.SOURCES['slides'])} | Homework files: "
      f"{len(agent.SOURCES['homework'])} | Books/other: {len(agent.SOURCES['other'])}")
print(f"Answer-key files hidden from the tutor: {len(agent.SOURCES['answers'])}")
print("\nRouSanGPT is ready!")
print("Type your question and press Enter.")
print("  /paste  - for text with several lines")
print("  /voice  - to ask with your microphone")
print("  quit    - to exit (or press Ctrl+C)")
print("Wait for the next 'You:' before typing again.\n")

session = agent.Session()
try:
    while True:
        question = read_question()
        if question.strip().lower() == "quit":
            print("Bye!")
            break
        if not question.strip():
            continue
        print("\n  (thinking...)", flush=True)
        try:
            result = session.ask(question)
            print("\nRouSanGPT:", result["reply"])
            if result["tools"]:
                print("\nTools used:", ", ".join(result["tools"]))
            print("\nSearched in:")
            for s in result["sources"]:
                print(f"  - [{s['kind']}] {s['source']} - {s['location']}")
            print()
        except Exception as e:
            print("\nSomething went wrong:", str(e)[:200], "\n")
except (KeyboardInterrupt, EOFError):
    print("\nBye!")