import json
data = json.load(open("waterloo_data.json"))
math239 = [c for c in data["courses"] if c.get("subjectCode")=="MATH" and c.get("catalogNumber")=="239"]
print(json.dumps(math239[0], indent=2))