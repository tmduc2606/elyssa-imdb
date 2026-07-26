"""Fix Cell 10 (Sample Efficiency) - restore broken rating loop."""
import json
from pathlib import Path

p = Path(r"C:\Users\Admin\Documents\GitHub\elyssa-imdb\data-science\notebooks\phase_2_duke_manual_analytics.ipynb")

with open(p, encoding='utf-8') as f:
    nb = json.load(f)

cell = nb['cells'][10]

# Rebuild the entire cell source from scratch
new_source = [
    "# ============================================================\n",
    "# 5.6 Sample Efficiency\n",
    "# ============================================================\n",
    "# Define sample sizes (fractions of training data)\n",
    "fracs = [0.2, 0.5, 0.8, 1.0]\n",
    'metrics = {"genre_f1": [], "rating_rmse": [], "rec_precision": []}\n',
    "\n",
    "# Genre: retrain Logistic Regression (simple) or GMU? We'll use logistic regression as proxy for speed.\n",
    "# But we should use the best model (GMU). For feasibility, we'll use Logistic Regression.\n",
    'X_train_genre = np.load(PROCESSED_DIR / "X_train_genre.npy")\n',
    'y_train_genre = np.load(PROCESSED_DIR / "y_train_genre.npy")\n',
    "for frac in fracs:\n",
    "    n = int(frac * len(X_train_genre))\n",
    "    idx = np.random.choice(len(X_train_genre), n, replace=False)\n",
    "    lr = OneVsRestClassifier(LogisticRegression(max_iter=1000, solver='liblinear'))\n",
    "    lr.fit(X_train_genre[idx], y_train_genre[idx])\n",
    "    pred = lr.predict(X_test_genre)\n",
    "    f1 = f1_score(y_test_genre, pred, average='macro')\n",
    '    metrics["genre_f1"].append(f1)\n',
    '    logger.info(f"Genre LR {frac}: F1={f1:.4f}")\n',
    "\n",
    "# Rating: retrain Ridge on tabular features only\n",
    "# X_train_rating is already loaded in the Data-Drift cell above\n",
    'y_train_rating = np.load(PROCESSED_DIR / "y_train_rating.npy")\n',
    "for frac in fracs:\n",
    "    n = int(frac * len(X_train_rating))\n",
    "    idx = np.random.choice(len(X_train_rating), n, replace=False)\n",
    "    ridge = RidgeCV(alphas=[1,10,100])\n",
    "    ridge.fit(X_train_rating[idx, :NUM_TAB], y_train_rating[idx])\n",
    "    pred = ridge.predict(X_test_rating[:, :NUM_TAB])\n",
    "    rmse = np.sqrt(mean_squared_error(y_test_rating, pred))\n",
    '    metrics["rating_rmse"].append(rmse)\n',
    '    logger.info(f"Rating Ridge {frac}: RMSE={rmse:.4f}")\n',
    "\n",
    "# Plot learning curves\n",
    "plt.figure()\n",
    "plt.plot(fracs, metrics[\"genre_f1\"], marker='o', label='Genre F1')\n",
    "plt.title('Sample Efficiency \u2011 Genre Classification')\n",
    "plt.xlabel('Training set fraction')\n",
    "plt.ylabel('Macro F1')\n",
    "plt.savefig(PROCESSED_DIR / 'sample_efficiency_genre.png')\n",
    "plt.savefig(PROCESSED_DIR / 'analytics_cell10.png', dpi=150, bbox_inches='tight')\n",
    "plt.close()\n",
    "\n",
    "plt.figure()\n",
    "plt.plot(fracs, metrics[\"rating_rmse\"], marker='o', label='Rating RMSE')\n",
    "plt.title('Sample Efficiency \u2011 Rating Regression')\n",
    "plt.xlabel('Training set fraction')\n",
    "plt.ylabel('RMSE')\n",
    "plt.savefig(PROCESSED_DIR / 'sample_efficiency_rating.png')\n",
    "plt.savefig(PROCESSED_DIR / 'analytics_cell10.png', dpi=150, bbox_inches='tight')\n",
    "plt.close()\n",
]

cell['source'] = new_source

with open(p, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

# Verify JSON
with open(p, encoding='utf-8') as f:
    json.load(f)
print("Cell 10 rebuilt. JSON valid: OK")

# Verify rating loop is intact
src = ''.join(cell['source'])
assert 'ridge.fit(X_train_rating[idx, :NUM_TAB], y_train_rating[idx])' in src, "MISSING: ridge.fit"
assert 'n = int(frac * len(X_train_rating))' in src, "MISSING: n calculation"
assert 'idx = np.random.choice(len(X_train_rating), n, replace=False)' in src, "MISSING: idx calculation"
assert 'X_train_rating = np.load' not in src, "BAD: X_train_rating reload still present"
print("All assertions passed")
