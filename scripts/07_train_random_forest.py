import importlib.util
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

if not cfg.TRAINING_TABLE.exists():
    raise FileNotFoundError(f"Missing training table. Run script 06 first: {cfg.TRAINING_TABLE}")

df = pd.read_csv(cfg.TRAINING_TABLE)
feature_names = list(cfg.PREDICTOR_RASTERS.keys())
required_columns = set(feature_names + ["label", "x", "y"])
missing_columns = required_columns.difference(df.columns)
if missing_columns:
    raise KeyError(f"Training table missing required columns: {sorted(missing_columns)}")

if df[feature_names + ["label", "x", "y"]].isna().any().any():
    raise ValueError("Training table contains missing values.")

X = df[feature_names]
y = df["label"].astype("uint8")

if y.nunique() < 2:
    raise ValueError("Training table must contain both positive and background labels.")

block_x = (df["x"] // cfg.SPATIAL_BLOCK_SIZE).astype(int)
block_y = (df["y"] // cfg.SPATIAL_BLOCK_SIZE).astype(int)
groups = block_x.astype(str) + "_" + block_y.astype(str)

splitter = GroupShuffleSplit(n_splits=50, test_size=0.25, random_state=cfg.RANDOM_STATE)
selected_split = None
for split_number, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups=groups), start=1):
    y_train_candidate = y.iloc[train_idx]
    y_test_candidate = y.iloc[test_idx]
    if y_train_candidate.nunique() == 2 and y_test_candidate.nunique() == 2:
        selected_split = (split_number, train_idx, test_idx)
        break

if selected_split is None:
    raise ValueError(
        "Could not create a spatial train/test split with both classes in each split. "
        "Try a smaller SPATIAL_BLOCK_SIZE or more positive labels."
    )

split_number, train_idx, test_idx = selected_split
X_train = X.iloc[train_idx]
X_test = X.iloc[test_idx]
y_train = y.iloc[train_idx]
y_test = y.iloc[test_idx]

print("Selected spatial split attempt:", split_number)
print("Train rows:", len(X_train))
print("Test rows:", len(X_test))
print("Train positives:", int(y_train.sum()))
print("Test positives:", int(y_test.sum()))

model = RandomForestClassifier(
    n_estimators=500,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=cfg.RANDOM_STATE,
    n_jobs=-1,
)

model.fit(X_train, y_train)

prob = model.predict_proba(X_test)[:, 1]
pred = model.predict(X_test)

roc_auc = roc_auc_score(y_test, prob)
average_precision = average_precision_score(y_test, prob)
report = classification_report(y_test, pred, zero_division=0)

importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": model.feature_importances_,
    }
).sort_values("importance", ascending=False)

joblib.dump(model, cfg.RANDOM_FOREST_MODEL)
importance.to_csv(cfg.FEATURE_IMPORTANCE, index=False)

with open(cfg.MODEL_METRICS, "w", encoding="utf-8") as f:
    f.write("Model: RandomForestClassifier\n")
    f.write(f"Selected spatial split attempt: {split_number}\n")
    f.write(f"Spatial block size m: {cfg.SPATIAL_BLOCK_SIZE}\n")
    f.write(f"Train rows: {len(X_train)}\n")
    f.write(f"Test rows: {len(X_test)}\n")
    f.write(f"Train positives: {int(y_train.sum())}\n")
    f.write(f"Test positives: {int(y_test.sum())}\n")
    f.write(f"ROC AUC: {roc_auc:.4f}\n")
    f.write(f"Average precision: {average_precision:.4f}\n\n")
    f.write(report)
    f.write("\n\nFeature importance:\n")
    f.write(importance.to_string(index=False))

print("ROC AUC:", roc_auc)
print("Average precision:", average_precision)
print(report)
print("Wrote:", cfg.RANDOM_FOREST_MODEL)
print("Wrote:", cfg.FEATURE_IMPORTANCE)
print("Wrote:", cfg.MODEL_METRICS)
