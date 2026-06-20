from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

SOURCES = ("chatgpt", "claude", "gemini", "perplexity", "serp", "reddit_search")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///:memory:"
    # Empty string disables the schema namespace (useful for SQLite tests).
    visibility_db_schema: str = "visibility"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    perplexity_api_key: str = ""

    anthropic_model: str = "claude-opus-4-7"
    openai_model: str = "gpt-4o"
    gemini_model: str = "gemini-1.5-pro"
    perplexity_model: str = "sonar"

    serp_backend: str = "serpapi"  # serpapi | brave
    serpapi_key: str = ""
    brave_api_key: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "visibility-tracker/0.1"

    cost_cap_chatgpt: int = 500
    cost_cap_claude: int = 1000
    cost_cap_gemini: int = 200
    cost_cap_perplexity: int = 200
    cost_cap_serp: int = 200
    cost_cap_reddit_search: int = 0

    cost_per_run_chatgpt: int = 5
    cost_per_run_claude: int = 20
    cost_per_run_gemini: int = 2
    cost_per_run_perplexity: int = 3
    cost_per_run_serp: int = 1
    cost_per_run_reddit_search: int = 0

    cost_cap_webhook_url: str = ""

    schedule_llm_hours: int = 24
    schedule_serp_hours: int = 168
    schedule_reddit_hours: int = 24
    schedule_tasks_hours: int = 24

    def cap_cents(self, source: str) -> int:
        return int(getattr(self, f"cost_cap_{source}", 0))

    def per_run_cents(self, source: str) -> int:
        return int(getattr(self, f"cost_per_run_{source}", 0))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
