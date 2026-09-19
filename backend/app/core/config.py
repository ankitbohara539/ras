from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sahayatri API"
    app_env: str = "development"
    api_prefix: str = "/api"
    frontend_url: str = "http://localhost:5173"

    database_url: str | None = None

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_photo_bucket: str = "ticket-photos"

    # Deduplication pipeline weights. They must sum to 1.0.
    dedupe_weight_category: float = 0.35
    dedupe_weight_text: float = 0.30
    dedupe_weight_image: float = 0.20
    dedupe_weight_geo: float = 0.15

    # A candidate is only written to duplicate_candidates above this score.
    dedupe_min_score: float = 0.45
    dedupe_max_candidates: int = 5

    # Corroborations needed before a ticket earns the community-verified badge.
    corroboration_threshold: int = 3

    # Age escalation. An unresolved ticket climbs the priority ladder on its
    # own, so a low-severity complaint cannot be ignored indefinitely:
    #   low -> medium after 7 days open
    #   medium -> high after a further 3 days (day 10 for a ticket born low,
    #             day 3 for one that was medium from the start)
    # Escalation stops at high. Critical is reserved for what is genuinely
    # dangerous, and age alone is not danger.
    escalate_low_to_medium_days: int = 7
    escalate_medium_to_high_days: int = 3

    # The public transparency page has no login, so it shows one municipality
    # rather than exposing every seeded municipality to an anonymous visitor.
    # A picker across municipalities is a real feature; this is the demo shape.
    public_stats_municipality_code: str = "KMC"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()
