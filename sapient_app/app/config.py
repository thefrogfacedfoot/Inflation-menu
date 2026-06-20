from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str

    anthropic_api_key: str
    scoring_model: str = "claude-opus-4-7"

    database_url: str

    poll_interval_minutes: int = 15
    dry_run: bool = False
    min_score_to_store: int = 60

    product_name: str
    product_description: str
    problem_keywords_raw: str = Field(alias="PROBLEM_KEYWORDS")
    seed_subreddits_raw: str = Field(alias="SEED_SUBREDDITS")
    discover_adjacent_subreddits: bool = True

    posts_per_listing: int = 25
    candidates_per_cycle: int = 40

    @property
    def problem_keywords(self) -> list[str]:
        return _csv(self.problem_keywords_raw)

    @property
    def seed_subreddits(self) -> list[str]:
        return _csv(self.seed_subreddits_raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
