from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CivicGrid API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_secret: str = "development-only-change-me"
    api_prefix: str = "/api/v1"
    database_url: str = "mysql+asyncmy://root:root@127.0.0.1:3306/smartcommunity"
    jwt_secret: str = "hrYB2QrOt8eKnKqoJ0eD2Es6uXCFmAuWl4nAuuZXpwc"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 15
    refresh_token_days: int = 14
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr = "noreply@example.com"
    smtp_from_name: str = "CivicGrid"
    smtp_reply_to: EmailStr | None = None
    smtp_security: Literal["starttls", "tls", "none"] = "starttls"
    smtp_timeout_seconds: float = 15.0
    redis_url: str | None = None
    geocoding_provider: str = "nominatim"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "CivicGrid-Kathmandu/0.3"
    nominatim_contact: str | None = None
    geocoding_country_codes: str = "np"
    geocoding_viewbox: str = "85.2630,27.7580,85.3860,27.6580"
    geocoding_bounded: bool = True
    object_storage_provider: str = "local"
    object_storage_path: str = "uploads"
    object_storage_endpoint: str | None = None
    object_storage_bucket: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    access_cookie_name: str = "civic_access"
    refresh_cookie_name: str = "civic_refresh"
    max_nearby_radius_meters: int = 25_000
    testing: bool = Field(default=False, exclude=True)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with /")
        return value.rstrip("/")

    @field_validator(
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_reply_to",
        "redis_url",
        "nominatim_contact",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("smtp_timeout_seconds")
    @classmethod
    def validate_smtp_timeout(cls, value: float) -> float:
        if not 1 <= value <= 120:
            raise ValueError("SMTP_TIMEOUT_SECONDS must be between 1 and 120")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",")]
        return [origin for origin in origins if origin]

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def nominatim_identity(self) -> str:
        identity = self.nominatim_user_agent.strip()
        if self.nominatim_contact:
            identity = f"{identity} (contact: {self.nominatim_contact.strip()})"
        return identity

    def validate_production_secrets(self) -> None:
        if self.app_env == "production" and (
            self.app_secret.startswith("development-")
            or self.jwt_secret.startswith("development-")
        ):
            raise RuntimeError("Production APP_SECRET and JWT_SECRET must be configured")
        if self.smtp_enabled and bool(self.smtp_username) != bool(self.smtp_password):
            raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        if self.app_env in {"staging", "production"} and not self.smtp_enabled:
            raise RuntimeError("SMTP_HOST must be configured outside development/test")
        using_public_nominatim = (
            self.geocoding_provider == "nominatim"
            and "nominatim.openstreetmap.org" in self.nominatim_base_url.lower()
        )
        if (
            self.app_env in {"staging", "production"}
            and using_public_nominatim
            and not self.nominatim_contact
        ):
            raise RuntimeError(
                "NOMINATIM_CONTACT must identify a real operator when using the public service"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_secrets()
    return settings
