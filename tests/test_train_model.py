from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import train_model


def write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def sample_records() -> list[dict[str, str]]:
    return [
        {"Issue": "A", "Consumer complaint narrative": "first XXXX complaint"},
        {"Issue": "A", "Consumer complaint narrative": "second complaint"},
        {"Issue": "B", "Consumer complaint narrative": "third complaint"},
        {"Issue": "B", "Consumer complaint narrative": "fourth complaint"},
        {"Issue": "C", "Consumer complaint narrative": "fifth complaint"},
    ]


def test_load_jsonl_training_data(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "training.jsonl"
    write_jsonl(path, sample_records())
    monkeypatch.setattr(train_model, "DATA_PATH", path)
    monkeypatch.setattr(train_model, "TRAINING_ROWS", 5)
    monkeypatch.setattr(train_model, "MAX_CLASSES", 2)

    data = train_model.load_training_data()
    assert set(data["Issue"]) == {"A", "B"}
    assert "[MASK]" in data.iloc[0]["clean_text"]


def test_load_csv_training_data(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "training.csv"
    pd.DataFrame(sample_records()).to_csv(path, index=False)
    monkeypatch.setattr(train_model, "DATA_PATH", path)
    monkeypatch.setattr(train_model, "TRAINING_ROWS", 5)
    monkeypatch.setattr(train_model, "MAX_CLASSES", 3)
    assert len(train_model.load_training_data()) == 5


def test_load_training_data_validation(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    monkeypatch.setattr(train_model, "DATA_PATH", missing)
    with pytest.raises(FileNotFoundError):
        train_model.load_training_data()

    one_class = tmp_path / "one.jsonl"
    write_jsonl(
        one_class,
        [{"Issue": "A", "Consumer complaint narrative": "only class"}],
    )
    monkeypatch.setattr(train_model, "DATA_PATH", one_class)
    monkeypatch.setattr(train_model, "TRAINING_ROWS", 10)
    monkeypatch.setattr(train_model, "MAX_CLASSES", 10)
    with pytest.raises(ValueError):
        train_model.load_training_data()


def test_main_trains_and_writes_metadata(monkeypatch, tmp_path: Path) -> None:
    data = pd.DataFrame(
        {
            "Issue": ["A", "B"],
            "clean_text": ["complaint a", "complaint b"],
        }
    )
    model_path = tmp_path / "model" / "classifier.joblib"
    metadata_path = tmp_path / "model" / "metadata.json"

    class FakeEncoder:
        def encode(self, texts, **kwargs):
            assert texts == ["complaint a", "complaint b"]
            assert kwargs["normalize_embeddings"] is True
            return np.array([[0.1, 0.2], [0.2, 0.1]])

    class FakeClassifier:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.classes_ = np.array(["A", "B"])
            self.fitted = False

        def fit(self, features, labels):
            assert features.shape == (2, 2)
            assert labels == ["A", "B"]
            self.fitted = True

    dumped = {}
    monkeypatch.setattr(train_model, "load_training_data", lambda: data)
    monkeypatch.setattr(train_model, "SentenceTransformer", lambda *_args, **_kwargs: FakeEncoder())
    monkeypatch.setattr(train_model, "MLPClassifier", FakeClassifier)
    monkeypatch.setattr(train_model, "MODEL_PATH", model_path)
    monkeypatch.setattr(train_model, "METADATA_PATH", metadata_path)
    monkeypatch.setattr(
        train_model.joblib,
        "dump",
        lambda model, path, compress: dumped.update(model=model, path=path, compress=compress),
    )

    train_model.main()

    assert dumped["path"] == model_path
    assert dumped["compress"] == 3
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["classes"] == ["A", "B"]
    assert metadata["training_rows"] == 2
