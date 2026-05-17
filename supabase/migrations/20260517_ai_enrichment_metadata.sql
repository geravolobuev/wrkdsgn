-- AI-enriched structured metadata for vacancies

alter table public.vacancies
  add column if not exists country text,
  add column if not exists city text,
  add column if not exists remote_type text,
  add column if not exists employment_type text,
  add column if not exists level text,
  add column if not exists role_type text,
  add column if not exists specializations text[] default '{}'::text[],
  add column if not exists semantic_tags text[] default '{}'::text[],
  add column if not exists tools text[] default '{}'::text[],
  add column if not exists language text[] default '{}'::text[],
  add column if not exists salary_min integer,
  add column if not exists salary_max integer,
  add column if not exists is_job boolean,
  add column if not exists enriched_at timestamptz,
  add column if not exists enrichment_version text,
  add column if not exists enrichment_hash text;

-- Enum-like checks (lightweight, easy to evolve)
alter table public.vacancies
  drop constraint if exists vacancies_remote_type_check;
alter table public.vacancies
  add constraint vacancies_remote_type_check
  check (remote_type is null or remote_type in ('remote','hybrid','onsite'));

alter table public.vacancies
  drop constraint if exists vacancies_employment_type_check;
alter table public.vacancies
  add constraint vacancies_employment_type_check
  check (employment_type is null or employment_type in ('full_time','part_time','contract','freelance','internship'));

alter table public.vacancies
  drop constraint if exists vacancies_level_check;
alter table public.vacancies
  add constraint vacancies_level_check
  check (level is null or level in ('intern','junior','middle','senior','lead','head','director'));

-- Indexes for fast structured filtering
create index if not exists vacancies_country_idx on public.vacancies(country);
create index if not exists vacancies_city_idx on public.vacancies(city);
create index if not exists vacancies_remote_type_idx on public.vacancies(remote_type);
create index if not exists vacancies_employment_type_idx on public.vacancies(employment_type);
create index if not exists vacancies_level_idx on public.vacancies(level);
create index if not exists vacancies_role_type_idx on public.vacancies(role_type);
create index if not exists vacancies_is_job_idx on public.vacancies(is_job);
create index if not exists vacancies_enriched_at_idx on public.vacancies(enriched_at desc);
create index if not exists vacancies_specializations_gin_idx on public.vacancies using gin(specializations);
create index if not exists vacancies_semantic_tags_gin_idx on public.vacancies using gin(semantic_tags);
create index if not exists vacancies_tools_gin_idx on public.vacancies using gin(tools);
create index if not exists vacancies_language_gin_idx on public.vacancies using gin(language);

-- Lightweight text search for normalized + raw text
create index if not exists vacancies_structured_search_idx
on public.vacancies
using gin (
  to_tsvector(
    'simple',
    coalesce(title,'') || ' ' ||
    coalesce(company,'') || ' ' ||
    coalesce(description,'') || ' ' ||
    coalesce(city,'') || ' ' ||
    coalesce(country,'')
  )
);
