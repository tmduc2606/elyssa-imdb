import yaml, json

with open("/opt/airflow/data-engineering/gold/sources.yml") as f:
    data = yaml.safe_load(f)

tables = data["sources"][0]["tables"]
names = [t["name"] for t in tables]
print("Source tables:", json.dumps(names, indent=2))

# Check if name_known_for_title has special chars
for t in tables:
    if t["name"] in ("name_profession", "name_known_for_title", "title_writer"):
        print(f"\n{t['name']}:")
        print(f"  type: {type(t['name'])}")
        print(f"  repr: {repr(t['name'])}")
        print(f"  bytes: {list(t['name'].encode('utf-8'))}")
        print(f"  keys: {list(t.keys())}")
