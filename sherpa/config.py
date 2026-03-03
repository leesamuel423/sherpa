from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = "groq"
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = ""
    max_attempts: int = 3
    wall_clock_limit_seconds: float = 60.0
    grounding_threshold: float = 75.0
    enable_llm_consistency_check: bool = False
    keyword_strategy: str = "llm"
    log_level: str = "INFO"
    api_timeout_seconds: float = 5.0

    enabled_sources: list[str] = ["wikipedia", "arxiv"]
    source_wikipedia_max_sentences: int = 10
    source_arxiv_max_results: int = 3
    source_hackernews_max_stories: int = 5


settings = Settings()
