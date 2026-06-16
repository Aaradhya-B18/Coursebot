from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "it works"}

@app.get("/square/{number}")
def square(number: int):
    answer = number * number
    return {"result": answer}

notes = []

@app.get("/notes")
def get_notes():
    return {"notes": notes}

@app.post("/notes")
def add_note(text:str):
    notes.append(text)
    return {"message": "added", "notes": notes}
