from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import get_type_hints


def _load_provider_base_module():
    module_path = Path(__file__).resolve().parents[1] / "pico" / "providers" / "base.py"
    spec = importlib.util.spec_from_file_location("_pico_provider_base_for_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_model_client_protocol_is_complete_model_contract() -> None:
    provider_base = _load_provider_base_module()

    assert get_type_hints(provider_base.complete_model)["model_client"] is provider_base.ModelClient
