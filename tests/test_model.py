"""
test_model.py — Unit Tests for ML Training Pipeline and Model Persistence

Run with: python -m pytest tests/test_model.py -v
"""

import sys
import os
import pytest
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import DATASET_DIR, MODELS_DIR, GESTURE_CLASSES, FEATURE_NAMES
from backend.train_model import (
    load_dataset_from_dir,
    extract_features_from_dataframe,
    split_by_session_or_group,
    train_gesture_model,
)


@pytest.fixture
def dataset_path(tmp_path):
    """
    Returns DATASET_DIR if CSVs exist; otherwise generates a temporary
    sample dataset fixture so unit tests pass reliably on fresh git clones.
    """
    csv_files = list(DATASET_DIR.glob("*.csv")) if DATASET_DIR.exists() else []
    if len(csv_files) > 0:
        return DATASET_DIR

    from backend.generate_sample_data import generate_full_dataset
    fixture_dir = tmp_path / "dataset"
    generate_full_dataset(
        output_dir=fixture_dir,
        participants=["P01"],
        sessions=["S01", "S02", "S03"],
        samples_per_gesture=20,
    )
    return fixture_dir


class TestModelPipeline:
    """Tests for model dataset loading, splitting, and training."""

    def test_load_dataset_from_dir(self, dataset_path):
        """Dataset directory should contain CSVs that load cleanly."""
        df = load_dataset_from_dir(dataset_path)
        assert len(df) > 0
        assert "gesture" in df.columns
        assert set(df["gesture"].unique()).issubset(set(GESTURE_CLASSES))

    def test_missing_dataset_dir_raises(self, tmp_path):
        """Empty directory should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_dataset_from_dir(tmp_path)

    def test_feature_extraction_matrix(self):
        """Feature matrix should have correct shape and no NaNs."""
        sample_df = pd.DataFrame([{
            "flex_thumb": 3200, "flex_index": 3200, "flex_middle": 3200,
            "flex_ring": 3200, "flex_little": 3200,
            "accel_x": 0.0, "accel_y": 0.0, "accel_z": 9.8,
            "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
            "gesture": "OPEN_PALM",
            "participant_id": "P01",
            "session_id": "S01",
        }])
        X, y = extract_features_from_dataframe(sample_df)
        assert X.shape == (1, len(FEATURE_NAMES))
        assert y[0] == "OPEN_PALM"
        assert not np.isnan(X).any()

    def test_session_split_no_leakage(self, dataset_path):
        """Hold-out session split must strictly prevent session leakage between train and test."""
        df = load_dataset_from_dir(dataset_path)
        train_df, test_df = split_by_session_or_group(df, group_col="session_id", test_group_val="S03")

        train_sessions = set(train_df["session_id"].unique())
        test_sessions = set(test_df["session_id"].unique())

        # No intersection between train and test sessions!
        assert len(train_sessions.intersection(test_sessions)) == 0
        assert "S03" in test_sessions
        assert "S03" not in train_sessions

    def test_train_gesture_model_saves_artifact(self, tmp_path, dataset_path):
        """Training pipeline must produce a valid joblib bundle with model and metadata."""
        output_model = tmp_path / "test_model.joblib"
        bundle = train_gesture_model(
            dataset_dir=dataset_path,
            output_model_path=output_model,
            split_by="session",
            test_session="S03",
            n_estimators=10,  # fast test
        )

        assert output_model.exists()
        assert "model" in bundle
        assert "feature_names" in bundle
        assert bundle["metrics"]["accuracy"] > 0.80
        assert set(bundle["classes"]) == set(GESTURE_CLASSES)

    def test_train_gesture_model_random_split(self, tmp_path, dataset_path):
        """Training pipeline supports random stratified split."""
        output_model = tmp_path / "test_model_random.joblib"
        bundle = train_gesture_model(
            dataset_dir=dataset_path,
            output_model_path=output_model,
            split_by="random",
            n_estimators=10,
        )
        assert output_model.exists()
        assert "accuracy" in bundle["metrics"]

