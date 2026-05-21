-- Final prune for current MVP contract.
-- Keeps only fields used by current ingestion + current frontend.

-- Drop columns not used in current logic
alter table public.vacancies
  drop column if exists company,
  drop column if exists salary,
  drop column if exists stack,
  drop column if exists contact,
  drop column if exists reposted_at,
  drop column if exists level,
  drop column if exists source_url,
  drop column if exists raw_saved_at,
  drop column if exists country,
  drop column if exists city,
  drop column if exists location,
  drop column if exists remote,
  drop column if exists tags,
  drop column if exists remote_type,
  drop column if exists role_type,
  drop column if exists specializations,
  drop column if exists semantic_tags,
  drop column if exists tools,
  drop column if exists language,
  drop column if exists salary_min,
  drop column if exists salary_max,
  drop column if exists raw_title,
  drop column if exists system_tags,
  drop column if exists ai_keywords,
  drop column if exists industry,
  drop column if exists company_type,
  drop column if exists company_name,
  drop column if exists confidence_score;

-- Drop legacy constraints/indexes that may reference removed columns
alter table public.vacancies drop constraint if exists vacancies_remote_type_check;
alter table public.vacancies drop constraint if exists vacancies_level_check;

drop index if exists vacancies_remote_idx;
drop index if exists vacancies_seniority_idx;
drop index if exists vacancies_tags_gin_idx;
drop index if exists vacancies_search_idx;
drop index if exists vacancies_country_idx;
drop index if exists vacancies_city_idx;
drop index if exists vacancies_remote_type_idx;
drop index if exists vacancies_level_idx;
drop index if exists vacancies_role_type_idx;
drop index if exists vacancies_specializations_gin_idx;
drop index if exists vacancies_semantic_tags_gin_idx;
drop index if exists vacancies_tools_gin_idx;
drop index if exists vacancies_language_gin_idx;
drop index if exists vacancies_structured_search_idx;
drop index if exists vacancies_system_tags_gin_idx;
drop index if exists vacancies_ai_keywords_gin_idx;
drop index if exists vacancies_source_channel_message_hash_key;

-- Keep and enforce current enum-like constraints
alter table public.vacancies drop constraint if exists vacancies_grade_check;
alter table public.vacancies add constraint vacancies_grade_check
  check (seniority is null or seniority in ('Junior','Middle','Senior','Lead','Head / Director','Unknown'));

alter table public.vacancies drop constraint if exists vacancies_employment_type_check;
alter table public.vacancies add constraint vacancies_employment_type_check
  check (employment_type is null or employment_type in ('Full-time','Part-time','Contract','Freelance','Internship','Unknown'));

alter table public.vacancies drop constraint if exists vacancies_work_format_check;
alter table public.vacancies add constraint vacancies_work_format_check
  check (work_format is null or work_format in ('Remote','Hybrid','On-site','Unknown'));

-- Ensure useful indexes exist for current reads
create index if not exists vacancies_is_job_idx on public.vacancies(is_job);
create index if not exists vacancies_created_at_idx on public.vacancies(created_at desc);
create index if not exists vacancies_published_at_idx on public.vacancies(published_at desc);
create index if not exists vacancies_source_channel_idx on public.vacancies(source_channel);
create index if not exists vacancies_enriched_at_idx on public.vacancies(enriched_at desc);
create index if not exists vacancies_pipeline_stage_idx on public.vacancies(pipeline_stage);
create index if not exists vacancies_filter_status_idx on public.vacancies(filter_status);
create index if not exists vacancies_canonical_title_idx on public.vacancies(canonical_title);
create index if not exists vacancies_seniority_idx on public.vacancies(seniority);
create index if not exists vacancies_work_format_idx on public.vacancies(work_format);
create index if not exists vacancies_employment_type_idx on public.vacancies(employment_type);
