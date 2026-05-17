alter table public.vacancies
  add column if not exists canonical_title text,
  add column if not exists raw_title text;

create index if not exists vacancies_canonical_title_idx on public.vacancies(canonical_title);

update public.vacancies
set canonical_title = coalesce(canonical_title, title),
    raw_title = coalesce(raw_title, raw_text)
where canonical_title is null or raw_title is null;
