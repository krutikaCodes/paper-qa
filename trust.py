from __future__ import annotations

import importlib.util
from pathlib import Path

_module_path = Path(__file__).resolve().parent / "src" / "paperqa" / "trust.py"
_spec = importlib.util.spec_from_file_location("paperqa_trust_impl", _module_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Could not load trust implementation from {_module_path}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

calculate_trust = _module.calculate_trust
score_trust = _module.score_trust
trust_score = _module.trust_score

__all__ = ["calculate_trust", "score_trust", "trust_score"]
