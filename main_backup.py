import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI
from google import genai
from sentence_transformers import SentenceTransformer, util
from supabase import create_client
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = SentenceTransformer("all-MiniLM-L6-v2")
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_query(q: str) -> str:
    # Insert a space between letters and digits so "CS245" -> "CS 245",
    # collapse extra spaces, and standardize a few separators.
    q = q.replace("-", " ")
    q = re.sub(r'([A-Za-z]+)\s*(\d+)', r'\1 \2', q)
    q = re.sub(r'\s+', ' ', q)
    return q.strip()


def find_codes(q: str):
    # Pull any course codes the user typed, e.g. "CS 245", "MATH 239", "STAT 230".
    # Returns them uppercased and normalized to "<SUBJECT> <NUMBER><optional letter>".
    matches = re.findall(r'([A-Za-z]{2,4})\s*(\d{3}[A-Za-z]?)', q)
    return [f"{subj.upper()} {num.upper()}" for subj, num in matches]


@app.post("/ask")
def ask(question: str):
    clean_question = normalize_query(question)

    # 1) Semantic search: get the closest courses by meaning.
    question_vector = model.encode(clean_question).tolist()
    result = supabase.rpc("match_courses", {
        "query_embedding": question_vector,
        "match_count": 4
    }).execute()

    retrieved = []
    seen_texts = set()
    for row in result.data:
        if row["text"] not in seen_texts:
            retrieved.append(row["text"])
            seen_texts.add(row["text"])

    # 2) Direct code lookup: if the user named a specific course code,
    #    guarantee that exact course is in the context, even if semantic
    #    search ranked something else higher.
    codes = find_codes(clean_question)
    for code in codes:
        exact = supabase.table("courses").select("text").eq("code", code).execute()
        for row in exact.data:
            if row["text"] not in seen_texts:
                retrieved.insert(0, row["text"])  # put the exact match first
                seen_texts.add(row["text"])

    context = "\n\n".join(retrieved)

    prompt = f"""Use the following information to answer the student's question.
Only use the information provided. If it doesn't contain the answer, say so.

Information:
{context}

Question: {clean_question}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return {"question": question, "answer": response.text, "sources": retrieved}