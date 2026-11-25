import json
import re
import time
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel

import gemini_client
import knowledge

client = gemini_client.LazyClient(timeout_ms=60000)   # uses the key from Settings or .env
MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]


# The exact shape (JSON schema) the AI must follow when it writes a quiz
class QuizQuestion(BaseModel):
    type: Literal["multiple_choice", "fill_in_the_blank", "packet_analysis"]
    question: str
    packet_capture: str      # only used for packet_analysis, otherwise empty
    options: list[str]       # only used for multiple_choice, otherwise empty
    correct_answer: str
    explanation: str


class Quiz(BaseModel):
    questions: list[QuizQuestion]


# The quiz currently being played. The answers live here, hidden from the AI.
_ACTIVE = {"questions": [], "answered": {}}


def _course_excerpts(topic):
    """Find course material about the topic: slides first, then books (never
    homework or answer keys)."""
    found = knowledge.search(topic, [("slides", knowledge.SOURCES["slides"], 4),
                                     ("other", knowledge.SOURCES["other"], 3)])
    return "\n\n".join(f"[{meta['source']} - {meta['location']}]\n{doc}" for _, doc, meta in found)


def _normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def create_quiz(topic: str, num_questions: int = 5, question_types: str = "mixed") -> dict:
    """Create a quiz for the student on a Computer Networks topic, based on the
    course materials. topic: for example 'TCP congestion control' or 'subnetting'.
    num_questions: from 1 to 10. question_types: 'multiple_choice',
    'fill_in_the_blank', 'packet_analysis' (questions about a Wireshark-style packet
    capture), or 'mixed' (all three). Returns the questions WITHOUT answers. Show
    the questions to the student one at a time, then use check_quiz_answer."""
    num_questions = max(1, min(int(num_questions), 10))
    if question_types not in ("multiple_choice", "fill_in_the_blank", "packet_analysis", "mixed"):
        question_types = "mixed"
    types_text = ("a mix of multiple_choice, fill_in_the_blank and packet_analysis"
                  if question_types == "mixed" else f"only {question_types}")

    context = _course_excerpts(topic)   # <-- this line was missing

    prompt = f"""You write quiz questions for a university Computer Networks course.
Topic: {topic}
Number of questions: {num_questions}
Question types: {types_text}

Use ONLY facts supported by these course excerpts:
{context}

Rules for each question type:
- multiple_choice: put exactly 4 options in "options" (plain text, no letters).
  "correct_answer" must be the exact text of the correct option.
  Leave "packet_capture" empty.
- fill_in_the_blank: the question contains a blank written as _____ .
  "correct_answer" is a short word or phrase. "options" is an empty list.
  "packet_capture" is empty.
- packet_analysis: "packet_capture" is a realistic Wireshark-style packet list
  (3 to 8 lines, with No., Source, Destination, Protocol, Length and Info).
  The question must point at ONE specific packet number and ask about ONE field
  of it, for example "In packet 2, which TCP flags are set?" or "What is the
  source IP of packet 3?". The answer must be a short value that is written
  exactly in the capture. Never ask vague questions. "options" is an empty list.
Every question needs a short "explanation". Do not repeat questions."""

    quiz = None
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Quiz,
                ),
            )
            quiz = Quiz.model_validate_json(response.text)
            break
        except Exception as e:
            print(f"  (quiz: {model} problem: {str(e)[:80]})")
            time.sleep(2)
    if quiz is None or not quiz.questions:
        return {"error": "Could not create the quiz right now. Please try again."}

    questions = [q.model_dump() for q in quiz.questions]
        # drop broken questions: a multiple-choice answer must be one of the options
    questions = [
        q for q in questions
        if q["type"] != "multiple_choice" or q["correct_answer"] in q["options"]
    ]
    if not questions:
        return {"error": "Could not create a good quiz. Please try again."}
    _ACTIVE["questions"] = questions
    _ACTIVE["answered"] = {}

    # save the full quiz (with answers) to a file: handy test cases for the report
    Path("quizzes").mkdir(exist_ok=True)
    saved = Path("quizzes") / f"quiz_{int(time.time())}.json"
    saved.write_text(json.dumps({"topic": topic, "questions": questions}, indent=2), encoding="utf-8")

    return {
        "saved_to": str(saved),
        "number_of_questions": len(questions),
        "questions": [
            {"number": i, "type": q["type"], "question": q["question"],
             "packet_capture": q["packet_capture"], "options": q["options"]}
            for i, q in enumerate(questions, start=1)
        ],
    }

def check_quiz_answer(question_number: int, student_answer: str) -> dict:
    """Check the student's answer to one question of the current quiz.
    question_number: the question's number, starting at 1. student_answer: what the
    student wrote (for multiple choice, a letter A-D or the option text). Returns
    whether it is correct, the correct answer, an explanation and the running score."""
    questions = _ACTIVE["questions"]
    if not questions:
        return {"error": "There is no active quiz. Create one first with create_quiz."}
    if not 1 <= question_number <= len(questions):
        return {"error": f"Question number must be between 1 and {len(questions)}."}
    q = questions[question_number - 1]

    given = student_answer.strip()
    if q["type"] == "multiple_choice" and len(given) == 1 and given.upper() in "ABCD":
        index = "ABCD".index(given.upper())
        if index < len(q["options"]):
            given = q["options"][index]

    correct = _normalize(given) == _normalize(q["correct_answer"])
    _ACTIVE["answered"][question_number] = correct
    score = sum(_ACTIVE["answered"].values())
    return {
        "correct": correct,
        "correct_answer": q["correct_answer"],
        "explanation": q["explanation"],
        "score_so_far": f"{score} correct out of {len(_ACTIVE['answered'])} answered "
                        f"(quiz has {len(questions)} questions)",
        "note": "For fill-in-the-blank or packet questions, if the student's wording "
                "differs but clearly means the same thing, treat it as correct.",
    }


# The list we give to the AI
QUIZ_TOOLS = [create_quiz, check_quiz_answer]


# Quick self-test: run `python quiz.py`
if __name__ == "__main__":
    result = create_quiz("TCP three-way handshake", 3, "mixed")
    print(json.dumps(result, indent=2))
    print(check_quiz_answer(1, "A"))