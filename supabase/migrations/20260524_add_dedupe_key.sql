alter table public.vacancies
  add column if not exists dedupe_key text;

create index if not exists vacancies_dedupe_key_idx
  on public.vacancies (dedupe_key);

