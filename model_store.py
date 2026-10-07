"""Save/load the model safely.

WARNING: joblib/pickle files can run arbitrary code when loaded. Only load a
model that YOU trained with train.py on this machine. Never load a
model.joblib someone sent you or one downloaded from the internet.

load_model() only accepts models/model.joblib inside this project, and only
if its SHA-256 matches the models/model.sha256 written by train.py.
"""
import hashlib
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "model.joblib"
HASH_PATH = MODEL_DIR / "model.sha256"


def _sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save_model(bundle):
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    HASH_PATH.write_text(_sha256(MODEL_PATH))


def load_model(path=MODEL_PATH):
    p = Path(path).resolve()
    if p != MODEL_PATH.resolve():
        raise RuntimeError(f"Refusing to load model from {p}: only {MODEL_PATH} is trusted.")
    if not HASH_PATH.exists() or HASH_PATH.read_text().strip() != _sha256(p):
        raise RuntimeError("Refusing to load model: missing or mismatched models/model.sha256. "
                           "Retrain locally with: python train.py")
    return joblib.load(p)
