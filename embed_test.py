from sentence_transformers import SentenceTransformer,util

model = SentenceTransformer("all-MiniLM-L6-v2")

sentences = [
    "MATH 136 Linear Algebra is really hard",
    "The dining hall food is pretty good",
    "I love playing cricket on weekends",
    "CS 234 covers data structures and algorithms",
    "Calculus was the toughest course I took",
]

sentence_vectors = model.encode(sentences)

query = 'is linear algebra a tough class'
query_vector = model.encode(query)

scores = util.cos_sim(query_vector, sentence_vectors)

print("Query:",query)
print()
for i in range(len(sentences)):
    print(round(scores[0][i].item(), 3), "->", sentences[i])
    

