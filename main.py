import os
import re
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from supabase import create_client
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


def embed(text: str):
    r = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    values = list(r.embeddings[0].values)
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request body: the new question plus the conversation so far.
class Turn(BaseModel):
    question: str
    answer: str


class AskRequest(BaseModel):
    question: str
    history: Optional[List[Turn]] = None


GREETING_TRIGGERS = [
    "hi", "hello", "hey", "yo", "help",
    "what can you do", "what can i ask", "who are you", "what is this",
    "what are you", "what do you do", "what subjects", "what courses",
    "im a uw student", "i am a uw student", "im a student", "i am a student",
]

# Words that signal a real course question even when no code is typed.
COURSE_WORDS = re.compile(
    r'\b(course|courses|class|classes|hard|easy|harder|easier|difficult|difficulty|'
    r'take|taking|took|prereq|prerequisite|prof|professor|exam|exams|midterm|final|'
    r'assignment|workload|enroll|stream|advanced|enriched|recommend|worth|'
    r'math|cs|stat|stats|calc|calculus|algebra|combinatorics|probability|logic|'
    r'linear|compiler|proof|proofs)\b',
    re.IGNORECASE
)


def is_greeting(q: str) -> bool:
    ql = q.lower().strip("?!. ")
    return any(ql == t or ql.startswith(t + " ") for t in GREETING_TRIGGERS)


def normalize_query(q: str) -> str:
    q = q.replace("-", " ")
    q = re.sub(r'([A-Za-z]+)\s*(\d+)', r'\1 \2', q)
    q = re.sub(r'\s+', ' ', q)
    return q.strip()


def find_codes(q: str):
    matches = re.findall(r'([A-Za-z]{2,4})\s*(\d{3}[A-Za-z]?)', q)
    return [f"{subj.upper()} {num.upper()}" for subj, num in matches]


def looks_like_course_question(q: str) -> bool:
    return bool(find_codes(normalize_query(q)) or COURSE_WORDS.search(q))


@app.post("/ask")
def ask(req: AskRequest):
    question = req.question
    history = req.history or []

    if is_greeting(question):
        intro = (
            "Hey there, Warrior! \U0001FAE1 I'm WatAsk \u2014 I give straight answers about "
            "Waterloo courses: how hard they are, what they cover, and what students "
            "actually say on UWFlow.\n\n"
            "Right now I know about 33 core first- and second-year courses:\n"
            "\u2022 MATH \u2014 135, 136, 137, 138, 127, 128, 145, 146, 147, 148, 235, 245, 237, 247, 239\n"
            "\u2022 CS \u2014 115, 116, 135, 145, 136, 136L, 146, 240, 241, 241E, 245, 245E, 246, 246E\n"
            "\u2022 STAT \u2014 230, 231, 240, 241\n\n"
            "Try asking things like \"is MATH 239 hard?\", \"should I take CS 245 or 245E?\", "
            "or \"which Calc 3 should I take?\""
        )
        return {"question": question, "answer": intro, "source_codes": [], "sources": []}

    if not history and not looks_like_course_question(question):
        return {
            "question": question,
            "answer": (
                "Appreciate it! \U0001F60A I'm best at course questions though \u2014 "
                "try asking me about a specific Waterloo course, like \"is MATH 239 hard?\" "
                "or \"should I take CS 245 or 245E?\""
            ),
            "source_codes": [],
            "sources": [],
        }

    clean_question = normalize_query(question)

    if history:
        search_text = normalize_query(history[-1].question) + " " + clean_question
    else:
        search_text = clean_question

    question_vector = embed(search_text)
    result = supabase.rpc("match_courses", {
        "query_embedding": question_vector,
        "match_count": 4
    }).execute()

    sources = []
    seen_codes = set()
    for row in result.data:
        code = row.get("code")
        if code and code not in seen_codes:
            sources.append({"code": code, "text": row["text"]})
            seen_codes.add(code)

    codes = find_codes(clean_question)
    for code in codes:
        exact = supabase.table("courses").select("code,text").eq("code", code).execute()
        for row in exact.data:
            if row["code"] not in seen_codes:
                sources.insert(0, {"code": row["code"], "text": row["text"]})
                seen_codes.add(row["code"])

    context = "\n\n".join(s["text"] for s in sources)

    convo = ""
    for turn in history:
        convo += f"Student: {turn.question}\nWatAsk: {turn.answer}\n\n"

    prompt = f"""You are WatAsk, answering a University of Waterloo student's question about courses.
Use ONLY the course information provided below. If it doesn't contain the answer, say so plainly.
Use the conversation so far to understand follow-up questions (e.g. "what about the advanced version?").

When you mention difficulty ratings, translate them into plain language instead of just quoting a percentage.
For an "easy" rating, phrase it as how students experienced it. For example:
- around 30% easy -> "most students found it quite hard"
- around 45-55% easy -> "students were split; many found it moderately challenging"
- around 70%+ easy -> "most students found it manageable"
Do the same for "liked" (how well-liked it is) and "useful" (how useful students found it).

Keep the answer to 2-4 sentences, direct and conversational, like a senior student giving honest advice.

Course information:
{context}

Conversation so far:
{convo if convo else "(none yet)"}
Current question: {clean_question}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    answer_text = response.text

    answer_upper = answer_text.upper()
    mentioned = [s["code"] for s in sources if s["code"].upper() in answer_upper]
    source_codes = mentioned if mentioned else [s["code"] for s in sources]

    return {
        "question": question,
        "answer": answer_text,
        "source_codes": source_codes,
        "sources": sources,
    }