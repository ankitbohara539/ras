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
    # At or above this score the new report is merged under the match straight
    # away, with no authority review. Below it, it stays a suggestion.
    dedupe_auto_merge_score: float = 0.80
    # GPS error allowance on the distance gate. Reports up to this far beyond
    # a category's match radius are still *suggested* to the officer (two
    # phones at one pothole often record points 60-100 m apart), but never
    # merged automatically -- only pairs inside the true radius are.
    dedupe_gps_slack_m: float = 40.0

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

    # Comment pressure. Every `urgent_commenters_per_level` distinct citizens
    # who comment that a ticket is urgent ("fix this soon", "major issue",
    # "चाँडै बनाउनुहोस्") raise it one level: 3 people -> +1, 6 -> +2.
    # Like age, this stops at high.
    urgent_commenters_per_level: int = 3

    # Reverse geocoding (coordinates -> place name). OpenStreetMap's Nominatim
    # is free and keyless but requires an identifying User-Agent and at most
    # one request a second; point this at a self-hosted instance for real load.
    geocoder_url: str = "https://nominatim.openstreetmap.org/reverse"
    geocoder_user_agent: str = "Sahayatri-civic-reporting/1.0"
    geocoder_timeout_s: float = 4.0

    # Routing for the hazard map's safer-route planner. Free key from
    # openrouteservice.org (about 2,000 routes a day). Empty = the hazard map
    # still works, route suggestions report "not configured".
    openrouteservice_api_key: str | None = None
    openrouteservice_url: str = "https://api.openrouteservice.org"
    openrouteservice_timeout_s: float = 10.0

    # Dashboard "briefing" button: an AI-written line summarising your own
    # reports and your ward (citizens), or your ward's open-report load and
    # queues (officers), from our own model rather than a third-party AI
    # product -- an open-weight instruct model hosted on Hugging Face's
    # router (router.huggingface.co, OpenAI-compatible), not tied to any one
    # provider. Free access token from huggingface.co/settings/tokens.
    #
    # Hugging Face's free monthly credit ($0.10) is enough to try this out,
    # not to run it for real traffic -- but specific model+provider pairings
    # are priced at $0 and shift over time (check
    # huggingface.co/docs/inference-providers/pricing). HUGGINGFACE_MODEL is
    # swappable for exactly that reason: point it at whichever pairing is
    # free right now without touching code.
    #
    # Empty = the button still works, with a templated line built from the
    # same numbers instead of AI prose -- see app.services.summary_service.
    huggingface_api_key: str | None = None
    # ":novita" pins the inference provider. Qwen3 is a reasoning model; its
    # hidden "thinking" is switched off per request (see app.core.huggingface)
    # so the whole token budget goes to the visible answer.
    huggingface_model: str = "Qwen/Qwen3.8-27B:novita"
    huggingface_api_url: str = "https://router.huggingface.co/v1"
    huggingface_timeout_s: float = 20.0
    # How long a generated briefing is reused before the next open refreshes
    # it, and the minimum gap between two manual "Regenerate" taps. Both
    # exist to protect a free/shared inference budget, the same way the
    # comment/OSM/Nominatim limits elsewhere in this file do.
    dashboard_summary_ttl_s: float = 600.0
    dashboard_summary_regenerate_cooldown_s: float = 60.0

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
