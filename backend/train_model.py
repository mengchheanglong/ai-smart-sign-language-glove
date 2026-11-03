"""
train_model.py — Machine Learning Training Pipeline for Gesture Recognition

Trains a Random Forest classifier on recorded glove sensor datasets.
Prevents data leakage by splitting on recording sessions / participants.
Extracts engineered features and saves model artifacts to models/gesture_model.joblib.

Team 2 — Senior Design Project
"""

import sys
import os
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Support running as a standalone script or imported module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score
from sklearn.model_selection import GroupShuffleSplit, GroupKFold

from backend.utils import (
    DATASET_DIR,
    MODELS_DIR,
    GESTURE_CLASSES,
    FEATURE_NAMES,
    extract_features,
)


def load_dataset_from_dir(dataset_dir: Path) -> pd.DataFrame:
    """
    Load and concatenate all CSV files in the dataset directory.
    """
    csv_files = list(dataset_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in dataset directory: {dataset_dir}")

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            # Ensure required columns exist
            if "gesture" in df.columns:
                dfs.append(df)
        except Exception as e:
            print(f"⚠️ Warning: Could not read {f.name}: {e}")

    if not dfs:
        raise ValueError(f"No valid gesture CSVs loaded from {dataset_dir}")

    full_df = pd.concat(dfs, ignore_index=True)
    # Filter to only known gesture classes
    full_df = full_df[full_df["gesture"].isin(GESTURE_CLASSES)]
    return full_df


def extract_features_from_dataframe(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply feature engineering to raw sensor dataframe.
    
    Returns:
        X (np.ndarray of shape [N, num_features]), y (np.ndarray of shape [N])
    """
    feature_rows = []
    labels = []

    for _, row in df.iterrows():
        feat_dict = extract_features(row)
        # Preserve strict order matching FEATURE_NAMES
        vec = [feat_dict[k] for k in FEATURE_NAMES]
        feature_rows.append(vec)
        labels.append(row["gesture"])

    X = np.array(feature_rows, dtype=np.float32)
    y = np.array(labels)
    return X, y


def split_by_session_or_group(
    df: pd.DataFrame,
    group_col: str = "session_id",
    test_group_val: str = "S03",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split dataset cleanly by session or participant to prevent data leakage.
    If the specified test_group_val is present, hold it out as test set.
    Otherwise, use GroupShuffleSplit.
    """
    if group_col in df.columns and test_group_val in df[group_col].values:
        train_df = df[df[group_col] != test_group_val].copy()
        test_df = df[df[group_col] == test_group_val].copy()
        if len(train_df) > 0 and len(test_df) > 0:
            print(f"  Hold-out split on {group_col}: Test = '{test_group_val}' ({len(test_df)} samples), Train = other ({len(train_df)} samples)")
            return train_df, test_df

    if group_col in df.columns and df[group_col].nunique() >= 2:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
        train_idx, test_idx = next(gss.split(df, groups=df[group_col]))
        train_df = df.iloc[train_idx].copy()
        test_df = df.iloc[test_idx].copy()
        print(f"  GroupShuffleSplit on {group_col}: Train = {len(train_df)}, Test = {len(test_df)}")
        return train_df, test_df
    else:
        # Fallback to random stratified split (or unstratified if min count < 2)
        from sklearn.model_selection import train_test_split
        min_class_count = df["gesture"].value_counts().min() if "gesture" in df.columns else 0
        stratify = df["gesture"] if min_class_count >= 2 else None
        train_df, test_df = train_test_split(df, test_size=0.25, random_state=42, stratify=stratify)
        print(f"  Fallback split: Train = {len(train_df)}, Test = {len(test_df)}")
        return train_df, test_df


def print_ascii_confusion_matrix(cm: np.ndarray, classes: List[str]):
    """Pretty prints confusion matrix table in terminal."""
    header = f"{'True / Pred':<14} | " + " | ".join(f"{c[:6]:>6}" for c in classes)
    sep = "-" * len(header)
    print("\nConfusion Matrix:")
    print(sep)
    print(header)
    print(sep)
    for i, row_class in enumerate(classes):
        row_vals = " | ".join(f"{cm[i][j]:>6d}" for j in range(len(classes)))
        print(f"{row_class:<14} | {row_vals}")
    print(sep)


def train_gesture_model(
    dataset_dir: Path = DATASET_DIR,
    output_model_path: Optional[Path] = None,
    split_by: str = "session",
    test_session: str = "S03",
    n_estimators: int = 100,
) -> Dict[str, Any]:
    """
    Main training routine:
    1. Load data
    2. Split to avoid leakage
    3. Feature extraction
    4. Model fit
    5. Evaluation & metrics
    6. Save joblib artifact
    """
    start_time = time.time()
    dataset_dir = Path(dataset_dir)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if output_model_path is None:
        output_model_path = MODELS_DIR / "gesture_model.joblib"
    else:
        output_model_path = Path(output_model_path)

    print("==================================================")
    print("  AI Smart Sign Language Glove — ML Training")
    print("  Team 2 — Senior Design Project")
    print("==================================================")
    print(f"Dataset path:    {dataset_dir}")
    print(f"Output artifact: {output_model_path}")
    print(f"Target classes:  {len(GESTURE_CLASSES)} gestures")

    # 1. Load data
    df = load_dataset_from_dir(dataset_dir)
    print(f"\nLoaded {len(df)} total samples from dataset files.")
    print("Class distribution:")
    for g, count in df["gesture"].value_counts().items():
        print(f"  {g:<14}: {count} samples")

    # 2. Split dataset by session or participant
    group_col = "participant_id" if split_by == "participant" else "session_id"
    train_df, test_df = split_by_session_or_group(df, group_col=group_col, test_group_val=test_session)

    # 3. Extract features
    print(f"\nExtracting {len(FEATURE_NAMES)} engineered features...")
    X_train, y_train = extract_features_from_dataframe(train_df)
    X_test, y_test = extract_features_from_dataframe(test_df)

    print(f"Training feature matrix: {X_train.shape}")
    print(f"Testing feature matrix:  {X_test.shape}")

    # 4. Train Random Forest Classifier
    print(f"\nTraining Random Forest ({n_estimators} trees)...")
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=16,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # 5. Evaluate
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")

    print("\n" + "=" * 50)
    print(f"  EVALUATION RESULTS (Tested on unseen {group_col})")
    print("=" * 50)
    print(f"Overall Accuracy: {acc * 100:.2f}%")
    print(f"Macro F1-Score:   {macro_f1:.4f}\n")

    # Use unique classes present in test/train to format report
    present_classes = sorted(list(set(y_test) | set(y_pred)))
    print("Classification Report:")
    print(classification_report(y_test, y_pred, labels=present_classes, target_names=present_classes, digits=3, zero_division=0))

    cm = confusion_matrix(y_test, y_pred, labels=present_classes)
    print_ascii_confusion_matrix(cm, present_classes)

    # Feature importances
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\nTop 5 Most Informative Features:")
    for rank in range(min(5, len(sorted_idx))):
        idx = sorted_idx[rank]
        print(f"  {rank+1}. {FEATURE_NAMES[idx]:<24} (importance: {importances[idx]:.4f})")

    # 6. Save model bundle
    bundle = {
        "model": clf,
        "feature_names": FEATURE_NAMES,
        "classes": GESTURE_CLASSES,
        "metrics": {
            "accuracy": float(acc),
            "macro_f1": float(macro_f1),
            "train_samples": int(len(train_df)),
            "test_samples": int(len(test_df)),
            "split_by": split_by,
        },
        "trained_at": datetime.now().isoformat(),
        "model_type": "RandomForestClassifier",
    }

    joblib.dump(bundle, output_model_path)
    elapsed = time.time() - start_time
    print(f"\n✅ Model artifact successfully saved to:\n   {output_model_path}")
    print(f"Completed in {elapsed:.2f} seconds.")

    return bundle


def main():
    parser = argparse.ArgumentParser(description="Sign Language Glove ML Model Trainer")
    parser.add_argument("--dataset-dir", type=str, default=str(DATASET_DIR), help="Path to CSV dataset folder")
    parser.add_argument("--output-model", type=str, default=str(MODELS_DIR / "gesture_model.joblib"), help="Path to save model")
    parser.add_argument("--split-by", type=str, choices=["session", "participant", "random"], default="session", help="Split strategy")
    parser.add_argument("--test-session", type=str, default="S03", help="Session ID held out for testing")
    parser.add_argument("--trees", type=int, default=100, help="Number of trees in Random Forest")
    args = parser.parse_args()

    train_gesture_model(
        dataset_dir=Path(args.dataset_dir),
        output_model_path=Path(args.output_model),
        split_by=args.split_by,
        test_session=args.test_session,
        n_estimators=args.trees,
    )


if __name__ == "__main__":
    main()

