"""Lazy imports for the optional provider SDK dependency group."""

from __future__ import annotations

from importlib import import_module, metadata
from types import ModuleType


PROVIDERS_EXTRA_COMMAND = "uv sync --extra providers"
OPENAI_SDK_VERSION = "2.46.0"
ANTHROPIC_SDK_VERSION = "0.117.0"


class ProviderSDKConfigurationError(RuntimeError):
    """Raised when a configured provider SDK is absent or has the wrong version."""


def load_openai_sdk() -> ModuleType:
    """Load the exact OpenAI SDK selected by the frozen transport decision."""

    return _load_exact_sdk("openai", OPENAI_SDK_VERSION)


def load_anthropic_sdk() -> ModuleType:
    """Load the exact Anthropic SDK selected by the frozen transport decision."""

    return _load_exact_sdk("anthropic", ANTHROPIC_SDK_VERSION)


def load_httpx() -> ModuleType:
    """Load the HTTP client supplied by the optional provider dependency group."""

    try:
        return import_module("httpx")
    except ImportError as exc:
        raise ProviderSDKConfigurationError(_missing_extra_message("httpx")) from exc


def _load_exact_sdk(package: str, expected_version: str) -> ModuleType:
    try:
        sdk = import_module(package)
    except ImportError as exc:
        raise ProviderSDKConfigurationError(_missing_extra_message(package)) from exc

    try:
        installed_version = metadata.version(package)
    except metadata.PackageNotFoundError as exc:
        raise ProviderSDKConfigurationError(_missing_extra_message(package)) from exc
    if installed_version != expected_version:
        raise ProviderSDKConfigurationError(
            f"Pico requires {package}=={expected_version} for native provider transport, "
            f"but found {installed_version}. Run `{PROVIDERS_EXTRA_COMMAND}` to restore the lock."
        )
    return sdk


def _missing_extra_message(package: str) -> str:
    return (
        f"The optional provider dependency {package!r} is not installed. "
        f"Run `{PROVIDERS_EXTRA_COMMAND}` before using native provider transport."
    )
