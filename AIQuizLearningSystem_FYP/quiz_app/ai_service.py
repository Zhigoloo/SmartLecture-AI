import io
import json
import re
import logging

import anthropic
from PyPDF2 import PdfReader
from docx import Document
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 50_000


class QuizGenerationError(Exception):
    """Raised when AI quiz generation fails."""
    pass


def extract_text_from_file(uploaded_file):
    """Extract text content from an uploaded PDF or DOCX file."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()

    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif name.endswith(".docx") or name.endswith(".doc"):
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(f"Unsupported file type: {name}. Please upload a PDF or DOCX file.")

    text = text.strip()
    if not text:
        raise ValueError("Could not extract any text from the uploaded file.")

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning("Lecture text truncated to %d characters.", MAX_TEXT_LENGTH)

    return text


def generate_quiz_questions(text, num_questions=10, instructions=""):
    """Call the Claude API to generate multiple-choice questions from lecture text."""
    if not settings.ANTHROPIC_API_KEY:
        raise QuizGenerationError(
            "Anthropic API key is not configured. "
            "Please set ANTHROPIC_API_KEY in your .env file."
        )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = (
        "You are an expert educational quiz generator. "
        "Given lecture notes or educational content, generate quiz questions "
        "that test understanding of the key concepts.\n\n"
        "Question formats you can generate:\n"
        "- Multiple-choice (default): each question has exactly 4 options\n"
        "- Yes/No or True/False: each question has exactly 2 options "
        "(either [\"Yes\", \"No\"] or [\"True\", \"False\"])\n\n"
        "If the teacher's instructions mention 'yes/no', 'yes or no', 'true/false', "
        "'true or false', or 'boolean' questions, generate questions with exactly 2 options "
        "using the matching wording (Yes/No or True/False). Otherwise, generate standard "
        "4-option multiple-choice questions. If the teacher mixes formats (e.g. "
        "'5 multiple choice and 5 yes/no'), follow their mix.\n\n"
        "Rules:\n"
        f"- Generate exactly {num_questions} questions by default (unless the teacher specifies a different number)\n"
        "- Each question must have either exactly 2 options (yes/no or true/false) or exactly 4 options (multiple choice)\n"
        "- Exactly one option per question must be correct\n"
        "- For yes/no or true/false questions, phrase the question as a statement or yes/no question "
        "(e.g. 'Is HTTPS encrypted?' or 'TCP is a connectionless protocol.')\n"
        "- Questions should test comprehension, not just memorization\n"
        "- Options should be plausible (avoid obviously wrong distractors)\n"
        "- Return ONLY valid JSON, no other text\n\n"
        "Return a JSON array with this exact structure:\n"
        "[\n"
        '  {\n'
        '    "question": "What is the primary purpose of...?",\n'
        '    "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        '    "correct_index": 0\n'
        '  },\n'
        '  {\n'
        '    "question": "Is HTTPS encrypted?",\n'
        '    "options": ["Yes", "No"],\n'
        '    "correct_index": 0\n'
        '  }\n'
        "]\n\n"
        "Where correct_index is the 0-based index of the correct option."
    )

    user_message = (
        f"Generate {num_questions} quiz questions "
        f"from the following lecture notes:\n\n---\n{text}\n---"
    )

    if instructions:
        user_message += (
            f"\n\nAdditional instructions from the teacher:\n{instructions}"
        )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        raise QuizGenerationError(f"AI API error: {e}") from e

    raw_text = response.content[0].text
    # Strip markdown code fences if present
    raw_text = re.sub(r"^```json?\s*", "", raw_text.strip())
    raw_text = re.sub(r"\s*```$", "", raw_text.strip())

    try:
        questions = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise QuizGenerationError(
            "Failed to parse AI response as JSON. Please try again."
        ) from e

    # Validate structure
    if not isinstance(questions, list):
        raise QuizGenerationError("AI response is not a list of questions.")

    for i, q in enumerate(questions):
        if not isinstance(q.get("question"), str):
            raise QuizGenerationError(f"Question {i + 1} is missing the 'question' field.")
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) not in (2, 4):
            raise QuizGenerationError(
                f"Question {i + 1} must have exactly 2 options (yes/no, true/false) or 4 options (multiple choice)."
            )
        ci = q.get("correct_index")
        if not isinstance(ci, int) or ci < 0 or ci >= len(opts):
            raise QuizGenerationError(f"Question {i + 1} has an invalid correct_index.")

    return questions
