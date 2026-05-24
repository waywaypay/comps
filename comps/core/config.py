from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://comps:comps@localhost:5432/comps"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    voyage_api_key: str = ""
    voyage_embed_model: str = "voyage-finance-2"
    voyage_rerank_model: str = "rerank-2"

    comps_api_host: str = "0.0.0.0"
    comps_api_port: int = 8000

    ingest_max_extract_chars: int = 60_000
    ingest_chunk_target_tokens: int = 400
    ingest_chunk_overlap_tokens: int = 50
    ingest_embed_batch: int = 128

    search_candidate_limit: int = 100
    search_fused_limit: int = 50
    search_rerank_topk: int = 10
    search_rrf_k: int = Field(default=60, description="RRF constant; 60 is canonical")

    embedding_dim: int = 1024


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
