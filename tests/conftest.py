"""Small fallbacks let static unit tests run in lean validation environments."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import sentence_transformers  # noqa: F401
except ModuleNotFoundError:
    module = types.ModuleType("sentence_transformers")

    class MissingSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("SentenceTransformer is not installed in this validation environment")

    module.SentenceTransformer = MissingSentenceTransformer
    sys.modules["sentence_transformers"] = module

try:
    import langdetect  # noqa: F401
except ModuleNotFoundError:
    module = types.ModuleType("langdetect")
    module.detect = lambda _text: "en"
    sys.modules["langdetect"] = module
