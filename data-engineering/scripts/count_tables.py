import yaml
with open("/opt/airflow/data-engineering/gold/sources.yml") as f:
    data = yaml.safe_load(f)
tables = data["sources"][0]["tables"]
print(f"Total tables: {len(tables)}")
for i, t in enumerate(tables):
    print(f"  {i}: {t['name']}")
