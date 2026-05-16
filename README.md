# Design Jobs MVP (Free Tier Only)

Minimal architecture:

Telegram channels -> Python scraper -> Supabase Postgres -> Next.js frontend

- Frontend hosting: Vercel free tier
- Scraper hosting: Render free tier (or GitHub Actions + cron-job.org)
- Database: Supabase free tier

## 1. Updated Architecture

- `src/main.py`: Telegram multi-channel scraper + deterministic classifier + dedup + normalized inserts
- `supabase/migrations/*.sql`: schema migration for web-facing jobs model
- `web/*`: Next.js App Router frontend with jobs feed, search, filters, job detail page

## 2. DB Schema (Supabase)

Run migration:

- `supabase/migrations/20260516_jobs_schema_mvp.sql`

Required fields in `vacancies` (MVP web):

- `id`
- `title`
- `company`
- `location`
- `remote`
- `seniority`
- `tags`
- `description`
- `source_channel`
- `source_link`
- `created_at`
- `slug`

## 3. Frontend Structure

- `web/app/page.tsx` -> `/`
- `web/app/jobs/page.tsx` -> `/jobs`
- `web/app/jobs/[slug]/page.tsx` -> `/jobs/[slug]`
- `web/components/*` -> cards, filters, pagination
- `web/lib/jobs.ts` -> Supabase search/filter queries

## 4. Supabase Setup

1. Run SQL migration in Supabase SQL Editor.
2. Enable read access for frontend (RLS policy) on `vacancies` for anon role.
3. Copy:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Example read policy (if RLS enabled):

```sql
alter table public.vacancies enable row level security;

create policy "vacancies_read_public"
on public.vacancies
for select
to anon
using (true);
```

## 5. Scraper Integration

The scraper keeps current architecture and now inserts normalized fields:

- `title, company, location, remote, seniority, tags, description, source_link, slug`
- preserves deterministic classification from `parser/job_classifier.py`
- preserves dedup:
  - by `(source_channel, source_message_id)`
  - by `content_hash` across channels

## 6. Frontend Pages

- `/` simple landing
- `/jobs` list + search + filters + pagination
- `/jobs/[slug]` full description + source link + metadata

## 7. Search & Filtering

Implemented via Supabase queries only (no paid tools):

- keyword (`q`) over `title/company/description`
- tag (`tag`)
- remote (`remote=true`)
- seniority (`seniority`)
- pagination (`page`)

## 8. Deployment Instructions

### Frontend (Vercel free)

1. Import repo in Vercel.
2. Set root directory: `web`.
3. Add env vars:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Deploy.

### Scraper (Render free, optional)

If you want scraper on Render free worker:

1. Create a new Background Worker from this repo root.
2. Build command:
   - `pip install -r requirements.txt`
3. Start command:
   - `python src/main.py`
4. Add env vars from `.env.example`.
5. Add external schedule (cron-job.org) that triggers GitHub Actions workflow (already used) or Render cron equivalent.

### Existing scheduler path (already working)

- Keep GitHub workflow dispatch + cron-job.org HTTP trigger.

## Local Run

### Scraper

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Frontend

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Open: `http://localhost:3000/jobs`
