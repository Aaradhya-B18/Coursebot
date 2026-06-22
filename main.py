import os
from dotenv import load_dotenv
from fastapi import FastAPI
from google import genai
from sentence_transformers import SentenceTransformer, util

load_dotenv()
client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = SentenceTransformer("all-MiniLM-L6-v2")

snippets = ["MATH 136 is Linear Algebra 1. Many students find the proofs challenging.",
    "CS 234 covers data structures and algorithms, taught in C.",
    "STAT 230 is an introductory probability course, considered fairly difficult.",
    "MATH 237 is Calculus 3, focusing on multivariable calculus.",
    "MUSIC 140 is a popular elective, often taken as an easy GPA booster.",
    ]

snippet_vectors = model.encode(snippets)

app = FastAPI()

@app.post("/ask")
def ask(question: str):
    question_vector = model.encode(question)
    scores = util.cos_sim(question_vector, snippet_vectors)[0]
    top_indices = scores.argsort(descending=True)[:2]
    retrieved = [snippets[i] for i in top_indices]

    context = "\n".join(retrieved)
    prompt = f"""use the following information to answer the student's question.
Only use the information, and if it doesen't contain the answer,say so.

Information:
{context}

Question: {question}
"""
    response = client.models.generate_content(
        model = "gemini-2.5-flash",
        contents = prompt
    )
    return {"question": question, "answer": response.text, "sources":retrieved}
