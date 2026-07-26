"""Retrain RidgeCV on tabular-only features and save."""
import json
import joblib
import numpy as np
from pathlib import Path
from sklearn.linear_model import RidgeCV

PROCESSED_DIR = Path(__file__).parent.parent / "marts" / "processed"

# Cell 6: Load data
X_train_full = np.load(PROCESSED_DIR / "X_train_rating.npy")
X_val_full   = np.load(PROCESSED_DIR / "X_val_rating.npy")
X_test_full  = np.load(PROCESSED_DIR / "X_test_rating.npy")
y_train = np.load(PROCESSED_DIR / "y_train_rating.npy")

with open(PROCESSED_DIR / "feature_columns.json") as f:
    feat_info = json.load(f)
tabular_feature_count = len(feat_info["tabular_features"])
X_train_rating_tab = X_train_full[:, :tabular_feature_count]
X_val_rating_tab   = X_val_full[:, :tabular_feature_count]
X_test_rating_tab  = X_test_full[:, :tabular_feature_count]

print(f"Training RidgeCV on {tabular_feature_count} tabular features")
print(f"X_train: {X_train_rating_tab.shape}, X_val: {X_val_rating_tab.shape}, X_test: {X_test_rating_tab.shape}")

# Cell 7: Ridge Regression (fixed)
ridge = RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0])
ridge.fit(X_train_rating_tab, y_train)
print(f"RidgeCV trained. Coefficients: {ridge.coef_.shape}, n_features_in_: {ridge.n_features_in_}")
print(f"Best alpha: {ridge.alpha_}")

# Cell 58: Save
joblib.dump(ridge, PROCESSED_DIR / "ridge_regression.pkl")
print("Saved ridge_regression.pkl")
