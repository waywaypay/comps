-- Initial schema for comps: sources, deals, chunks, and eval tables.
--
-- Two non-obvious choices:
--   - chunk-level embeddings so one doc can match on multiple sections
--   - generated-always tsvector so BM25 and vector stay in lockstep

create extension if not exists vector;
create extension if not exists pg_trgm;

create table sources (
    id         bigserial primary key,
    uri        text        not null,
    kind       text        not null,
    fetched_at timestamptz not null default now(),
    sha256     text        not null unique
);

create table deals (
    id              bigserial primary key,
    source_id       bigint references sources(id),
    target_name     text   not null,
    target_ticker   text,
    buyer_name      text,
    buyer_type      text,
    deal_type       text,
    sector_gics     text,
    sub_sector      text,
    country         text,
    region          text,
    announced_on    date,
    closed_on       date,
    revenue_usd     numeric,
    ebitda_usd      numeric,
    ebitda_margin   numeric,
    ev_usd          numeric,
    ev_revenue_mult numeric,
    ev_ebitda_mult  numeric,
    growth_yoy      numeric,
    thesis          text,
    meta            jsonb       not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

create index deals_sector_idx     on deals (sector_gics);
create index deals_revenue_idx    on deals (revenue_usd);
create index deals_announced_idx  on deals (announced_on);
create index deals_buyer_type_idx on deals (buyer_type);
create index deals_region_idx     on deals (region);

create table chunks (
    id        bigserial primary key,
    deal_id   bigint  not null references deals(id) on delete cascade,
    source_id bigint  not null references sources(id),
    section   text    not null,
    page      int,
    ord       int     not null,
    text      text    not null,
    tokens    int     not null,
    embedding vector(1024) not null,
    tsv       tsvector generated always as (to_tsvector('english', text)) stored
);

create index chunks_embedding_idx on chunks
    using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index chunks_tsv_idx     on chunks using gin (tsv);
create index chunks_deal_idx    on chunks (deal_id);
create index chunks_section_idx on chunks (section);

-- Eval set: queries plus per-deal graded judgments.
create table eval_queries (
    id      bigserial primary key,
    query   text  not null,
    filters jsonb not null default '{}'::jsonb
);

create table eval_judgments (
    query_id bigint references eval_queries(id) on delete cascade,
    deal_id  bigint references deals(id)        on delete cascade,
    grade    int   not null check (grade between 0 and 3),
    primary key (query_id, deal_id)
);
