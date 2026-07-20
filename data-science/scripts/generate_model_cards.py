import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

TEMPLATE = """# Model Card: {name}

## Overview
- **Task:** {pillar}
- **Architecture:** {model_type}
- **Version:** 1.0
- **Date:** {date}

## Training Data
- **Source:** Gold layer Parquet exports
- **Sample:** {sample_percent}% development mode
- **Temporal Split:** Train < 2015, Val 2015-2018, Test 2019+

## Performance
| Metric | Value |
|--------|-------|
{metrics_table}

## Intended Use
- **Primary:** Film genre recommendation for web application
- **Secondary:** Analytical insights for content strategy

## Limitations
- Trained on IMDb English-language titles
- Cold-start performance limited for new users
- Temporal bias toward pre-2019 content

## Ethical Considerations
- No PII in training data
- Genre labels reflect IMDb categorization (may contain biases)
- Rating predictions are estimates, not guarantees

{citation}
"""


def generate_model_card(entry: dict, output_dir: Path, sample_percent: int = 5):
    name = entry["name"]
    pillar = entry.get("pillar", "Unknown")
    model_type = entry.get("type", "Unknown")
    metrics = entry.get("metrics", {})
    citation = entry.get("citation", "")

    metrics_table = "\n".join(
        f"| {k} | {v} |" for k, v in metrics.items()
    )

    card = TEMPLATE.format(
        name=name,
        pillar=pillar,
        model_type=model_type,
        date=datetime.now().strftime("%Y-%m-%d"),
        sample_percent=sample_percent,
        metrics_table=metrics_table,
        citation=f"\n## References\n{citation}" if citation else "",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name.replace('/', '_')}.md"
    with open(path, "w") as f:
        f.write(card)

    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate model cards from model_inventory.json")
    parser.add_argument("--inventory", default="marts/processed/model_inventory.json")
    parser.add_argument("--output-dir", default="docs/model_cards")
    parser.add_argument("--sample-percent", type=int, default=5)
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(f"Inventory not found: {inventory_path}")
        sys.exit(1)

    with open(inventory_path) as f:
        inventory = json.load(f)

    output_dir = Path(args.output_dir)
    for entry in inventory:
        path = generate_model_card(entry, output_dir, args.sample_percent)
        print(f"  Generated: {path}")


if __name__ == "__main__":
    main()
