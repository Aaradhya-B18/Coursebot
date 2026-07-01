import os, requests, json, time

headers = {"x-api-key": os.environ["UW_API_KEY"]}
BASE = "https://openapi.data.uwaterloo.ca/v3"
TARGET_SUBJECTS = ["MATH", "CS", "STAT"]
TERMS = ["1265", "1269", "1271", "1275"]   # Spring26, Fall26, Winter27, Spring27 — add more as they open

# subjects don't change per term, fetch once
subjects = requests.get(f"{BASE}/Subjects", headers=headers).json()
print(f"Subjects fetched: {len(subjects)}")

all_courses = []
for term_code in TERMS:
    print(f"\nTerm {term_code}:")
    for subj in TARGET_SUBJECTS:
        r = requests.get(f"{BASE}/Courses/{term_code}/{subj}", headers=headers)
        if r.status_code == 200:
            courses = r.json()
            for c in courses:
                c["_termCode"] = term_code   # tag which term it came from
            all_courses.extend(courses)
            print(f"  {subj}: {len(courses)}")
        else:
            print(f"  {subj}: ERROR {r.status_code}")
        time.sleep(1)

with open("waterloo_data.json", "w") as f:
    json.dump({"subjects": subjects, "courses": all_courses}, f, indent=2)
print(f"\nSaved {len(all_courses)} total course records to waterloo_data.json")