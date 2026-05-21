# Design Jobs MVP (Hard Reset)

Minimal architecture:

Telegram `@bbe_jobs` -> AI filter + role extraction (single prompt) -> Supabase -> Next.js frontend

## Current MVP Rules

- One source channel only: `@bbe_jobs`.
- AI is the only filter.
- Rejected posts are not saved.
- Accepted posts are saved with:
  - `role` -> `title`, `canonical_title`, `display_title`
  - `grade` -> `seniority`
  - `employment_type`, `work_format`
- Prompt source: `job-enrichment.prompt.txt` (repo root).

## Core Files

- `src/main.py` — ingestion loop and save logic.
- `job_parser/openrouter_client.py` — OpenRouter call + strict JSON validation.
- `job-enrichment.prompt.txt` — single source of filtering/extraction logic.

## Database Reset

To clear old data:

- `supabase/migrations/20260520_mvp_reset_truncate_vacancies.sql`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```
