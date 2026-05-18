-- Remove legacy enrichment/filtering columns no longer used by AI-only pipeline.

-- Drop old constraints/indexes tied to legacy columns first.
alter table public.vacancies drop constraint if exists vacancies_remote_type_check;
alter table public.vacancies drop constraint if exists vacancies_level_check;

drop index if exists vacancies_remote_idx;
drop index if exists vacancies_seniority_idx;
drop index if exists vacancies_tags_gin_idx;
drop index if exists vacancies_remote_type_idx;
drop index if exists vacancies_level_idx;
drop index if exists vacancies_role_type_idx;
drop index if exists vacancies_specializations_gin_idx;
drop index if exists vacancies_semantic_tags_gin_idx;
drop index if exists vacancies_tools_gin_idx;
drop index if exists vacancies_language_gin_idx;

-- Drop legacy columns.
alter table public.vacancies
  drop column if exists remote,
  drop column if exists tags,
  drop column if exists remote_type,
  drop column if exists level,
  drop column if exists role_type,
  drop column if exists specializations,
  drop column if exists semantic_tags,
  drop column if exists tools,
  drop column if exists language;
