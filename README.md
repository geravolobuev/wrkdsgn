# Design Jobs MVP (Free Tier Only)

Architecture:

Telegram channels -> deterministic pre-filter -> OpenRouter enrichment (ingestion only) -> Supabase -> Next.js frontend

## Key Rules

- AI runs only during ingestion.
- Frontend filtering/search reads structured DB fields only.
- No vectors, no embeddings infra, no RAG, no paid search.

## 1) Architecture Changes

- `parser/deterministic_prefilter.py` rejects obvious non-job content before AI calls.
- `src/enrichment/openrouter_client.py` performs strict JSON enrichment via OpenRouter free models.
- `src/main.py` uses cache/version logic and never re-enriches unchanged posts.
- `web/app/api/jobs/route.ts` filters by structured metadata columns.

## 2) DB Schema Updates

Run migrations in order:

- `supabase/migrations/20260516_jobs_schema_mvp.sql`
- `supabase/migrations/20260517_ai_enrichment_metadata.sql`

New structured metadata fields include:

- `country`, `city`
- `remote_type`, `employment_type`, `level`, `role_type`
- `specializations[]`, `semantic_tags[]`, `tools[]`, `language[]`
- `salary_min`, `salary_max`
- `enriched_at`, `enrichment_version`, `enrichment_hash`, `is_job`

## 3) Taxonomy System

Defined in `src/enrichment/taxonomy.py`:

- Levels
- Specializations
- Employment types
- Remote types
- Role types
- Semantic tags
- Tools
- Languages

AI output is validated against these fixed enums.

## 4) Deterministic Classifier

`parser/deterministic_prefilter.py`

- regex + keyword score + metadata heuristics
- rejects obvious non-job posts
- dramatically reduces AI calls

## 5) OpenRouter Enrichment Module

`src/enrichment/openrouter_client.py`

- OpenRouter only
- configurable model
- fallback models
- timeout + retries + 429 backoff
- strict JSON parsing + enum validation

## 6) Enrichment Cache Logic

`src/main.py`

Uses:

- `content_hash`
- `enrichment_hash`
- `enrichment_version`
- `enriched_at`

Enrichment is skipped when unchanged and same version.

## 7) Scraper Integration

Pipeline in `src/main.py`:

- fetch post
- deterministic pre-filter
- AI enrichment (if enabled)
- normalize structured metadata
- insert/update Supabase

## 8) Frontend Filtering Updates

`web/components/jobs-feed-client.tsx` and `web/app/api/jobs/route.ts`

Filters now target structured fields:

- specialization
- level
- city
- country
- remote_type
- employment_type

## 9) Search Updates

Search is Postgres-based only (`ilike` over normalized columns + description). No semantic runtime AI.

## 10) Setup / Deployment

### Scraper env (repo root)

From `.env.example`:

- `TG_API_ID`, `TG_API_HASH`, `SOURCE_CHANNELS`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `ENABLE_AI_ENRICHMENT=true`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `ENRICHMENT_VERSION`

### GitHub Actions secrets

Set the same values in repository secrets for scheduled/manual ingestion runs.

### Frontend env (`web/.env.local` / Vercel)

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### Run locally

Scraper:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

Frontend:

```bash
cd web
npm install
npm run dev
```
