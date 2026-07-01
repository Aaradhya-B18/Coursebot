import json

data = json.load(open("waterloo_data.json"))

# dedupe by subject+catalogNumber, collect terms offered
courses = {}
for c in data["courses"]:
    key = f"{c['subjectCode']} {c['catalogNumber']}"
    if key not in courses:
        courses[key] = {
            "code": key,
            "title": c["title"],
            "description": c["description"],
            "requirements": c.get("requirementsDescription", ""),
            "subject": c["subjectCode"],
            "catalogNumber": c["catalogNumber"],
            "termsOffered": [],
        }
    t = c["_termCode"]
    if t not in courses[key]["termsOffered"]:
        courses[key]["termsOffered"].append(t)

clean = sorted(courses.values(), key=lambda x: x["code"])
with open("planner_courses.json", "w") as f:
    json.dump(clean, f, indent=2)

print(f"Cleaned: {len(clean)} unique courses")
print("Example:", json.dumps(clean[0], indent=2))