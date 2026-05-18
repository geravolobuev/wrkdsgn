-- Structured enrichment pipeline fields (raw + filtered + enriched in one row)

alter table public.vacancies
  add column if not exists canonical_title text,
  add column if not exists display_title text,
  add column if not exists seniority text,
  add column if not exists work_format text,
  add column if not exists system_tags text[] default '{}'::text[],
  add column if not exists ai_keywords text[] default '{}'::text[],
  add column if not exists industry text,
  add column if not exists company_type text,
  add column if not exists company_name text,
  add column if not exists confidence_score numeric,
  add column if not exists filter_status text,
  add column if not exists filter_reason text,
  add column if not exists pipeline_stage text,
  add column if not exists raw_saved_at timestamptz;

create index if not exists vacancies_pipeline_stage_idx on public.vacancies(pipeline_stage);
create index if not exists vacancies_filter_status_idx on public.vacancies(filter_status);
create index if not exists vacancies_system_tags_gin_idx on public.vacancies using gin(system_tags);
create index if not exists vacancies_ai_keywords_gin_idx on public.vacancies using gin(ai_keywords);
