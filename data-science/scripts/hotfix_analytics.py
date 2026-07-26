"""Apply hotfixes to phase_2_duke_manual_analytics.ipynb for memory overflow."""
import json
from pathlib import Path

NOTEBOOK = Path(r"C:\Users\Admin\Documents\GitHub\elyssa-imdb\data-science\notebooks\phase_2_duke_manual_analytics.ipynb")

with open(NOTEBOOK, encoding='utf-8') as f:
    nb = json.load(f)

fixes_applied = []

for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell['source'])

    # ──────────────────────────────────────────────
    # FIX 1 (Cell 7.3): Move DistilBERT loading outside predict()
    # ──────────────────────────────────────────────
    if 'create_inference_fn' in src and 'ThreadPoolExecutor' in src:
        new_source = []
        for line in cell['source']:
            stripped = line.lstrip()
            if stripped.startswith('# Real DistilBERT inference'):
                continue
            if stripped.startswith('from transformers import DistilBertTokenizer'):
                continue
            if stripped.startswith('_tokenizer = DistilBertTokenizer'):
                continue
            if stripped.startswith('_bert_model = DistilBertModelHF'):
                continue
            if stripped.startswith('_bert_model.eval()'):
                continue
            new_source.append(line)

        final_source = []
        for line in new_source:
            final_source.append(line)
            if line.strip() == 'model.eval()':
                final_source.append('\n')
                final_source.append("    # Load DistilBERT once for text embeddings (reused across all predictions)\n")
                final_source.append("    from transformers import DistilBertTokenizer, DistilBertModel as DistilBertModelHF\n")
                final_source.append("    _tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')\n")
                final_source.append("    _bert_model = DistilBertModelHF.from_pretrained('distilbert-base-uncased').to(DEVICE)\n")
                final_source.append("    _bert_model.eval()\n")
                final_source.append('\n')

        cell['source'] = final_source
        src = ''.join(final_source)
        fixes_applied.append(f"Cell {i}: Moved DistilBERT loading outside predict() closure")

    # ──────────────────────────────────────────────
    # FIX 2 (Cell 7.3): Reduce sequential iterations 100 -> 10
    # ──────────────────────────────────────────────
    if 'create_inference_fn' in src and 'range(100)' in src and 'ThreadPoolExecutor' in src:
        new_source = []
        for line in cell['source']:
            if line.strip() == 'for _ in range(100):':
                new_source.append(line.replace('range(100)', 'range(10)'))
            else:
                new_source.append(line)
        cell['source'] = new_source
        src = ''.join(new_source)
        fixes_applied.append(f"Cell {i}: Reduced sequential iterations from 100 to 10")

    # ──────────────────────────────────────────────
    # FIX 3 (Cell 7.3): Reduce max_workers 100 -> 10
    # ──────────────────────────────────────────────
    if 'ThreadPoolExecutor' in src:
        new_source = []
        for line in cell['source']:
            if 'max_workers=100' in line:
                new_source.append(line.replace('max_workers=100', 'max_workers=10'))
            else:
                new_source.append(line)
        cell['source'] = new_source
        fixes_applied.append(f"Cell {i}: Reduced ThreadPoolExecutor max_workers from 100 to 10")

    # ──────────────────────────────────────────────
    # FIX 4 (Cell 7.3): Reduce concurrent range 100 -> 10
    # ──────────────────────────────────────────────
    if 'ThreadPoolExecutor' in src:
        new_source = []
        for line in cell['source']:
            if 'results = list(executor.map(single_request, range(100)))' in line:
                new_source.append(line.replace('range(100)', 'range(10)'))
            else:
                new_source.append(line)
        cell['source'] = new_source
        fixes_applied.append(f"Cell {i}: Reduced concurrent requests from 100 to 10")

    # ──────────────────────────────────────────────
    # FIX 5 (Cell 10 / Sample Efficiency): Remove duplicate X_train_rating reload
    # (Cell 9 / Data-Drift already loaded it)
    # ──────────────────────────────────────────────
    if 'Sample Efficiency' in src:
        new_source = []
        for line in cell['source']:
            stripped = line.strip()
            # Remove duplicate X_train_rating reload (uses double quotes in source)
            if 'X_train_rating' in stripped and 'np.load' in stripped:
                continue
            new_source.append(line)
        removed = len(cell['source']) - len(new_source)
        if removed > 0:
            cell['source'] = new_source
            fixes_applied.append(f"Cell {i}: Removed duplicate X_train_rating reload (already in scope from Data-Drift cell)")

# Write back
with open(NOTEBOOK, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("=== Hotfixes Applied ===")
for fix in fixes_applied:
    print(f"  - {fix}")
print(f"\nTotal: {len(fixes_applied)} fixes")

# Verify JSON
with open(NOTEBOOK, encoding='utf-8') as f:
    json.load(f)
print("JSON valid: OK")
