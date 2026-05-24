import os

os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("VOYAGE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://comps:comps@localhost:5432/comps_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
