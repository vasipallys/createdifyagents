"""Application configuration loaded from environment variables.

All provider/model/key settings live here and are read once at startup via
``get_settings()``. Tests can call ``get_settings.cache_clear()`` after
mutating the environment.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Enums / constants
# ---------------------------------------------------------------------------
Provider = Literal["groq", "openai", "claude", "glm"]
ExecutionMode = Literal["http", "slim"]


class ModelSpec(BaseModel):
    """Resolved provider + model + credentials bundle handed to the engine."""

    provider: Provider
    model: str
    base_url: str = ""
    api_key: str = ""
    api_version: str = ""          # Anthropic version header
    organization: str = ""         # OpenAI org header
    temperature: float = 0.2
    max_tokens: int = 2400


# ---------------------------------------------------------------------------
# Jira multi-instance config
# ---------------------------------------------------------------------------
JiraAuthType = Literal["pat", "basic"]


class JiraInstance(BaseModel):
    name: str
    base_url: str
    version: Literal["v2", "v3"] = "v3"
    auth_type: JiraAuthType = "pat"
    email: str = ""
    token: str = ""
    username: str = ""
    password: str = ""

    @property
    def rest_root(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/{self.version}"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Provider / execution mode
    llm_provider: Provider = "openai"
    llm_execution_mode: ExecutionMode = "http"

    # Model ids
    groq_model: str = "llama-3.3-70b-versatile"
    openai_model: str = "gpt-4o-mini"
    claude_model: str = "claude-3-5-sonnet-20241022"
    glm_model: str = "glm-4-flash"

    # Generation
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2400

    # --- Groq ---
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_organization: str = ""

    # --- Claude / Anthropic ---
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_version: str = "2023-06-01"

    # --- GLM (Zhipu) ---
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # --- Graphon / Slim ---
    slim_mode: str = "local"
    slim_plugin_folder: str = ".slim/plugins"
    slim_binary_path: str = ""
    slim_daemon_addr: str = ""
    slim_daemon_key: str = ""
    slim_marketplace_url: str = "https://marketplace.dify.ai"

    # --- Jira ---
    jira_instances: str = ""

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "*"

    # --- OpenTelemetry / Arize Phoenix ---
    phoenix_enabled: bool = True
    phoenix_collector_endpoint: str = "http://127.0.0.1:6006/v1/traces"
    phoenix_ui_url: str = "http://127.0.0.1:6006"
    phoenix_project_name: str = "story-pointer"
    phoenix_api_key: str = ""
    phoenix_batch: bool = True
    phoenix_capture_content: bool = False
    phoenix_working_dir: str = ".phoenix"

    # ----- validators / derived helpers -----
    @field_validator("llm_provider", mode="after")
    @classmethod
    def _lower_provider(cls, v: Provider) -> Provider:
        return v  # Literal already constrains; kept for clarity

    def model_spec(self) -> ModelSpec:
        """Build the provider-specific ``ModelSpec`` for the active provider."""
        p = self.llm_provider
        if p == "groq":
            return ModelSpec(
                provider="groq", model=self.groq_model,
                base_url=self.groq_base_url, api_key=self.groq_api_key,
                temperature=self.llm_temperature, max_tokens=self.llm_max_tokens,
            )
        if p == "openai":
            return ModelSpec(
                provider="openai", model=self.openai_model,
                base_url=self.openai_base_url, api_key=self.openai_api_key,
                organization=self.openai_organization,
                temperature=self.llm_temperature, max_tokens=self.llm_max_tokens,
            )
        if p == "glm":
            return ModelSpec(
                provider="glm", model=self.glm_model,
                base_url=self.glm_base_url, api_key=self.glm_api_key,
                temperature=self.llm_temperature, max_tokens=self.llm_max_tokens,
            )
        if p == "claude":
            return ModelSpec(
                provider="claude", model=self.claude_model,
                base_url=self.anthropic_base_url, api_key=self.anthropic_api_key,
                api_version=self.anthropic_api_version,
                temperature=self.llm_temperature, max_tokens=self.llm_max_tokens,
            )
        raise ValueError(f"Unknown provider: {p}")

    def jira_config(self) -> list[JiraInstance]:
        """Parse ``JIRA_INSTANCES`` JSON into typed instances."""
        raw = (self.jira_instances or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JIRA_INSTANCES is not valid JSON: {exc}") from exc
        if not isinstance(data, list):
            raise ValueError("JIRA_INSTANCES must be a JSON array")
        return [JiraInstance(**item) for item in data]

    def jira_instance(self, name: str) -> JiraInstance | None:
        for inst in self.jira_config():
            if inst.name == name:
                return inst
        return None

    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_provider_ready(self) -> None:
        """Raise a clear error if the chosen provider's key is missing."""
        spec = self.model_spec()
        if not spec.api_key:
            raise RuntimeError(
                f"LLM_PROVIDER='{self.llm_provider}' but its API key is not set. "
                f"Set the corresponding *_API_KEY in your environment."
            )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the settings cache (used by tests)."""
    get_settings.cache_clear()


__all__ = [
    "ExecutionMode",
    "JiraInstance",
    "ModelSpec",
    "Provider",
    "Settings",
    "get_settings",
    "reset_settings_cache",
]


# Quiet "imported but unused" linters for re-exported names under some checkers.
_ = Any
_ = os
_ = Field
