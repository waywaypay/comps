# Deploying comps to production

Recommended stack: **Fly.io** (api + worker) + **Neon** (Postgres with
pgvector) + **Upstash** (serverless Redis). All three have free tiers
that fit a starter deployment.

Total setup time: ~20 minutes the first time.

## 1. Provision Postgres on Neon

[neon.tech](https://neon.tech) → create project → choose region matching
your Fly region (e.g. `aws-us-east-1` ↔ Fly `iad`).

```bash
# Enable pgvector. From the Neon SQL editor or psql:
create extension if not exists vector;
create extension if not exists pg_trgm;
```

Copy the connection string. It looks like:
`postgresql://user:pass@ep-xyz.us-east-1.aws.neon.tech/comps?sslmode=require`

> **Why not Fly Postgres**: Fly's managed Postgres doesn't ship with
> pgvector. You can install it yourself, but Neon hands you both
> pgvector and connection pooling out of the box.

## 2. Provision Redis on Upstash

[upstash.com](https://upstash.com) → create Redis database → same region.

Copy the connection string. It looks like:
`rediss://default:pw@gusc1-tidy-mollusk-12345.upstash.io:12345`

> arq uses Redis as a job queue. Upstash's free tier (10k commands/day)
> easily covers thousands of ingest jobs.

## 3. Get API keys

- **Venice** (LLM): [venice.ai](https://venice.ai) → API keys
- **Voyage** (embeddings + rerank): [dash.voyageai.com](https://dash.voyageai.com)

## 4. Install flyctl and log in

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

## 5. Create the two Fly apps

```bash
fly apps create comps-api
fly apps create comps-worker
```

Edit `deploy/fly.api.toml` and `deploy/fly.worker.toml` if you want a
different region than `iad` — match your Neon and Upstash regions.

## 6. Set secrets on both apps

```bash
DB_URL='postgresql://user:pass@...neon.tech/comps?sslmode=require'
REDIS_URL='rediss://default:pw@...upstash.io:12345'
LLM_KEY='your-venice-key'
VOY_KEY='your-voyage-key'

for app in comps-api comps-worker; do
  fly secrets set -a "$app" \
    DATABASE_URL="$DB_URL" \
    REDIS_URL="$REDIS_URL" \
    LLM_API_KEY="$LLM_KEY" \
    VOYAGE_API_KEY="$VOY_KEY"
done
```

## 7. Deploy

```bash
fly deploy -c deploy/fly.api.toml      # runs `comps migrate` as release_command
fly deploy -c deploy/fly.worker.toml
```

The api's `release_command` runs migrations against Neon before the new
machines accept traffic. The worker starts pulling from Redis as soon
as it boots.

## 8. Verify

```bash
curl https://comps-api.fly.dev/healthz
# {"status":"ok"}

curl 'https://comps-api.fly.dev/search?q=vertical+SaaS+PE+buyout' | jq
# [] until you ingest something
```

## 9. Ingest documents

Two options. **From your laptop**, enqueue jobs that the deployed
worker will pick up:

```bash
# Point your local env at the deployed Redis
export REDIS_URL='rediss://default:pw@...upstash.io:12345'
export DATABASE_URL='postgresql://...neon.tech/comps?sslmode=require'
export LLM_API_KEY='...'  VOYAGE_API_KEY='...'

comps ingest *.pdf --kind 10-K   # default --enqueue
```

Or **inline on the worker machine**:

```bash
fly ssh console -a comps-worker
# inside the container:
comps ingest /path/to/doc.pdf --inline --kind memo
```

## 10. Hook the CLI to the deployed API

If you don't want to expose Postgres credentials to laptops, run the
CLI in client mode against the deployed API:

```bash
# (not built yet — file an issue if you want this. Today the CLI talks
# directly to Postgres via DATABASE_URL.)
```

Until that's built, share `DATABASE_URL` with anyone who needs
read-only CLI access.

## Continuous deployment

`.github/workflows/deploy.yml` deploys both apps on every push to
`main`. To enable it, set `FLY_API_TOKEN` in your GitHub repo secrets:

```bash
fly tokens create deploy -x 999999h | gh secret set FLY_API_TOKEN
```

## Scaling

- API: bump `min_machines_running` in `deploy/fly.api.toml` for more
  concurrency. The hybrid SQL is the bottleneck under load; consider a
  Neon read replica before adding API machines.
- Worker: `fly scale count 3 -a comps-worker` to ingest in parallel.
  arq distributes jobs across workers automatically.
- Postgres: Neon scales storage automatically. CPU/RAM is a one-click
  bump.

## Cost estimate (small / medium / large)

| Tier   | Deals  | Fly        | Neon       | Upstash | LLM+embed   | Total/mo |
|--------|--------|------------|------------|---------|-------------|----------|
| Small  | 1K     | $0 free    | $0 free    | $0 free | $5 ingest   | ~$5      |
| Medium | 25K    | $25        | $20        | $10     | $100 ingest | ~$155    |
| Large  | 100K+  | $100       | $100       | $25     | $400 ingest | ~$625    |

Ongoing serving cost is dominated by reranker calls: ~$0.003/query at
voyage-rerank-2. 10k searches/day = ~$1/day.

## Disaster recovery

- **Backups**: Neon snapshots are automatic (point-in-time recovery on
  the paid tier).
- **Re-embed**: if you swap embedding models, run `comps reindex`
  (TODO — single arq job that re-embeds all chunks).
- **Re-extract**: source bytes are hashed in `sources.sha256`. To
  re-extract with a new prompt, drop the deal rows and re-enqueue the
  source URIs; the upsert in `sources` won't duplicate.
