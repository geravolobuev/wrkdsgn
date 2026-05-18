-- Prompt contract v2 no longer returns these optional fields.
-- Keep only columns used by current AI output + app.

alter table public.vacancies
  drop column if exists system_tags,
  drop column if exists ai_keywords,
  drop column if exists industry,
  drop column if exists company_type,
  drop column if exists company_name,
  drop column if exists confidence_score;

drop index if exists vacancies_system_tags_gin_idx;
drop index if exists vacancies_ai_keywords_gin_idx;
