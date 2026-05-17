# Design Jobs MVP (Free Tier Only)

Architecture:

Telegram channels -> deterministic pre-filter -> OpenRouter enrichment (ingestion only) -> Supabase -> Next.js frontend

## Key Rules

- AI runs only during ingestion.
- Frontend filtering/search reads structured DB fields only.
- No vectors, no embeddings infra, no RAG, no paid search.

## 1) Architecture Changes

- `parser/job_classifier.py` applies deterministic score gate: `JOB` / `AD` / `UNCERTAIN`.
- `parser/ad_classifier.py` detects ad/funnel patterns (courses, registration campaigns).
- `parser/job_splitter.py` splits multi-job digests into one record per role.
- `parser/role_extractor.py` extracts canonical profession title.
- `parser/taxonomy_mapper.py` maps roles to strict allowed specializations.
- `parser/openrouter_client.py` handles OpenRouter fallback and uncertain AI classifier.
- `src/main.py` runs strict multi-stage ingestion with per-split idempotent hash.
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

`parser/job_classifier.py`

- score >= 3 => `JOB`
- score <= 0 => `AD`
- score in [1,2] => `UNCERTAIN` then AI `JOB/AD` classifier

## 5) OpenRouter Modules

`parser/openrouter_client.py`

- OpenRouter only
- fixed fallback chain (llama -> qwen -> gemma, optional `openrouter/free`)
- timeout + per-model retries
- strict JSON-only parsing + schema validation
- deterministic fallback object when all models fail
- uncertain-case classifier returns strict `JOB` / `AD`

## 6) Enrichment Cache Logic

`src/main.py`

Uses:

- `content_hash`
- `enrichment_hash`
- `enrichment_version`
- `enriched_at`
- split jobs hash includes source + message + split index + text

Enrichment is skipped when unchanged and same version.

## 7) Scraper Integration

Pipeline in `src/main.py`:

- fetch post
- deterministic score gate
- AI fallback classifier only for uncertain posts
- ad/funnel guard
- multi-job split
- canonical role extraction
- strict taxonomy mapping
- location extraction
- OpenRouter enrichment merge
- insert/upsert Supabase

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
- `OPENROUTER_TIMEOUT=10`
- `OPENROUTER_MAX_RETRIES=1`
- optional: `OPENROUTER_INCLUDE_GENERIC_FALLBACK=true`
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
