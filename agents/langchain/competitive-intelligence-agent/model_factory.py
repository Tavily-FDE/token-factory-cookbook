"""Provider-aware chat model construction."""

from __future__ import annotations

from langchain_nebius import ChatNebius
from langchain_openai import ChatOpenAI

SUPPORTED_PROVIDERS = {"nebius", "openai"}


def split_model_spec(model_name: str | None, *, default_provider: str = "nebius") -> tuple[str, str]:
    """Return `(provider, model)` from `provider:model` or a bare model name."""
    if not model_name or not model_name.strip():
        raise ValueError("A model name is required.")

    raw = model_name.strip()
    if ":" in raw:
        provider, model = raw.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if provider in SUPPORTED_PROVIDERS and model:
            return provider, model

    provider = default_provider.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported default model provider: {default_provider}")
    return provider, raw


def model_provider(model_name: str | None, *, default_provider: str = "nebius") -> str:
    """Return the provider implied by a model spec."""
    provider, _ = split_model_spec(model_name, default_provider=default_provider)
    return provider


def build_chat_model(model_name: str | None, *, default_provider: str = "nebius"):
    """Build a LangChain chat model from a provider-aware model spec."""
    provider, model = split_model_spec(model_name, default_provider=default_provider)
    if provider == "openai":
        return ChatOpenAI(model=model)
    if provider == "nebius":
        return ChatNebius(model=model)
    raise ValueError(f"Unsupported model provider: {provider}")
