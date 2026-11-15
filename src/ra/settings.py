"""Runtime settings, read once from the environment (12-factor). No secrets have defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    env: str = field(default_factory=lambda: _env("RA_ENV", "dev"))
    data_dir: Path = field(default_factory=lambda: Path(_env("RA_DATA_DIR", str(REPO_ROOT / ".ra"))))
    db_path: str = field(default_factory=lambda: _env("RA_DB_PATH", ""))
    release: str = field(default_factory=lambda: _env("RA_RELEASE", "0.2.0"))
    base_url: str = field(default_factory=lambda: _env("RA_BASE_URL", "http://localhost:8080"))

    # Authentication. With RA_OIDC_ISSUER set, tokens from that identity provider are verified
    # against its JWKS and the built-in identity provider is switched off.
    oidc_issuer: str = field(default_factory=lambda: _env("RA_OIDC_ISSUER"))
    oidc_audience: str = field(default_factory=lambda: _env("RA_OIDC_AUDIENCE", "revenue-assurance"))
    oidc_jwks_url: str = field(default_factory=lambda: _env("RA_OIDC_JWKS_URL"))
    oidc_roles_claim: str = field(default_factory=lambda: _env("RA_OIDC_ROLES_CLAIM", "roles"))
    token_ttl_s: int = field(default_factory=lambda: int(_env("RA_TOKEN_TTL_S", "1800")))
    max_login_failures: int = 5
    lockout_s: int = 300

    # Model access: "offline" runs the deterministic reasoner; "bedrock" calls Amazon Bedrock.
    llm_mode: str = field(default_factory=lambda: _env("RA_LLM_MODE", "offline"))
    bedrock_triage_model: str = field(default_factory=lambda: _env("RA_BEDROCK_TRIAGE_MODEL"))
    bedrock_reason_model: str = field(default_factory=lambda: _env("RA_BEDROCK_REASON_MODEL"))
    case_token_budget: int = field(default_factory=lambda: int(_env("RA_CASE_TOKEN_BUDGET", "60000")))

    # Integrations
    partner_a2a_url: str = field(default_factory=lambda: _env("RA_PARTNER_A2A_URL"))
    partner_a2a_token: str = field(default_factory=lambda: _env("RA_PARTNER_A2A_TOKEN"))
    plugins_config: Path = field(
        default_factory=lambda: Path(_env("RA_PLUGINS_CONFIG", str(REPO_ROOT / "config" / "plugins.yaml")))
    )
    skills_dir: Path = field(default_factory=lambda: Path(_env("RA_SKILLS_DIR", str(REPO_ROOT / "skills"))))
    baseline_config: Path = field(default_factory=lambda: REPO_ROOT / "config" / "baseline.yaml")

    # Workflow thresholds (base currency)
    investigate_min_variance: float = 500.0
    triage_confidence_floor: float = 0.80

    otlp_endpoint: str = field(default_factory=lambda: _env("OTEL_EXPORTER_OTLP_ENDPOINT"))

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_path:
            self.db_path = str(self.data_dir / "ra.db")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Used by tests after changing the environment."""
    global _settings
    _settings = None
