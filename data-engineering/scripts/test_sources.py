import yaml

with open("/opt/airflow/data-engineering/gold/sources.yml") as f:
    data = yaml.safe_load(f)
src = data["sources"][0]
tables = {t["name"] for t in src["tables"]}
print("All tables:", sorted(tables))
print("name_known_for_title found:", "name_known_for_title" in tables)
