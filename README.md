# comps

Financial deal comparables search. Hybrid BM25 + vector retrieval over
financial documents (10-K, S-1, press releases, deal memos, CIMs).

- Postgres 16 + pgvector + pg_trgm + built-in FTS — one system, joins are free
- voyage-finance-2 embeddings (1024-d, asymmetric)
- Cross-encoder rerank via voyage-rerank-2
- Claude Sonnet 4.6 (via Venice or any OpenAI-compatible endpoint) for structured extraction and NL query understanding
- Docling for PDF parsing (tables preserved), trafilatura for HTML
- FastAPI + Uvicorn surface, arq workers, Typer CLI
- Eval harness with nDCG@10 / recall@20 gate in CI

## Quickstart

```bash
cp .env.example .env  # fill in API keys
docker compose -f docker/docker-compose.yml up -d postgres redis
pip install -e ".[dev]"
comps migrate
comps ingest deal_memo.pdf --inline   # or run a worker and --enqueue
comps search "vertical SaaS PE buyout in europe, 2021-2024"
comps show 1
comps why 1 2
```

## Layout

```
comps/
├── pyproject.toml
├── docker/                  # api + worker images, compose
├── migrations/              # forward-only Postgres SQL migrations
├── comps/
│   ├── ingest/              # parse, chunk, extract, embed, pipeline
│   ├── search/              # understand, retrieve, rerank, service (FastAPI)
│   ├── eval/                # dataset, metrics, run, CI gate
│   ├── cli/                 # Typer CLI
│   ├── db/                  # pool + queries + migrate
│   └── core/                # config, logging, shared pydantic models
└── tests/
```

## Pipelines

### Ingest

`parse → chunk → extract → embed → index`. Each stage runs as an arq job;
failures are isolated and re-runnable. Re-ingest by sha256 is free.

- Chunks are section-aware (thesis / mdna / risks / financials / other).
- Extraction enforces refuse-on-uncertainty: null beats a guessed number.
- Currency normalized in-prompt to absolute USD; percentages as decimals.
- Embeddings are batched 128 per Voyage call; deterministic from text + model
  version, so a model swap is a single re-embed job from day 1.

### Search

`understand → embed query → hybrid SQL (BM25 ⊕ vector via RRF) → rerank`.

The hybrid SQL runs in a single round-trip with three CTEs (filters, BM25,
vector). RRF k=60 is the canonical default. The reranker sees a snippet
composed of `{target} ({year}) — {thesis}\n\n{best chunk}` so it judges a
coherent paragraph, not a fragment.

Latency budget per query: ~340ms p50, well under 1s p95.

## Eval

Golden set lives in `eval_queries` / `eval_judgments`. Build it with end-user
sessions: 20 queries per user, grade the top 20 from a BM25 baseline on a
0–3 scale, refresh quarterly.

```bash
comps eval --out report.json
python -m comps.eval.gate \
    --baseline baseline.json --candidate candidate.json \
    --min-ndcg-delta -0.01
```

CI gates PRs on nDCG@10 regression; without this, prompt drift will quietly
degrade the system inside of a month.

## Configuration

All configuration via env or `.env`. See `.env.example`. The settings object
in `comps/core/config.py` is the source of truth.

## Deploy

Production deploy on Fly.io + Neon (Postgres+pgvector) + Upstash (Redis):
see [deploy/DEPLOY.md](deploy/DEPLOY.md). GitHub Actions auto-deploys
both apps on push to `main` once `FLY_API_TOKEN` is set and
`DEPLOY_ENABLED` repo variable is `true`.
