import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "benchmark_ingestion.py"


def load_benchmark_module():
    spec = importlib.util.spec_from_file_location("quantcore_benchmark_ingestion", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_benchmark_requires_explicit_target(monkeypatch):
    module = load_benchmark_module()
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        module.parse_args()

    assert exc_info.value.code == 2


def test_benchmark_accepts_deterministic_cohort_target(monkeypatch):
    module = load_benchmark_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--cohort-size", "25"],
    )

    args = module.parse_args()

    assert args.cohort_size == 25
    assert args.symbols is None
    assert args.limit is None


def test_benchmark_rejects_multiple_targets(monkeypatch):
    module = load_benchmark_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--cohort-size", "25", "--limit", "25"],
    )

    with pytest.raises(SystemExit) as exc_info:
        module.parse_args()

    assert exc_info.value.code == 2


def test_benchmark_accepts_force_sync(monkeypatch):
    module = load_benchmark_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--cohort-size", "1", "--force-sync"],
    )

    args = module.parse_args()

    assert args.cohort_size == 1
    assert args.force_sync is True
    assert args.all is False


def test_benchmark_rejects_force_sync_with_all(monkeypatch):
    module = load_benchmark_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--cohort-size", "1", "--all", "--force-sync"],
    )

    with pytest.raises(SystemExit) as exc_info:
        module.parse_args()

    assert exc_info.value.code == 2
