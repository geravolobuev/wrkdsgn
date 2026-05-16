-- MVP schema normalization for design jobs web app

alter table public.vacancies
  add column if not exists title text,
  add column if not exists company text,
  add column if not exists location text,
  add column if not exists remote boolean,
  add column if not exists seniority text,
  add column if not exists tags text[] default '{}'::text[],
  add column if not exists description text,
  add column if not exists source_link text,
  add column if not exists slug text;

-- Keep backward compatibility with old source_url if present.
update public.vacancies
set source_link = coalesce(source_link, source_url)
where source_link is null;

update public.vacancies
set description = coalesce(description, raw_text)
where description is null;

-- Best-effort slug backfill for existing rows
update public.vacancies
set slug = lower(
  regexp_replace(
    coalesce(title, 'job') || '-' || coalesce(source_message_id::text, id::text),
    '[^a-zA-Z0-9]+',
    '-',
    'g'
  )
)
where slug is null;

create unique index if not exists vacancies_slug_key on public.vacancies(slug);
create index if not exists vacancies_created_at_idx on public.vacancies(created_at desc);
create index if not exists vacancies_remote_idx on public.vacancies(remote);
create index if not exists vacancies_seniority_idx on public.vacancies(seniority);
create index if not exists vacancies_source_channel_idx on public.vacancies(source_channel);
create index if not exists vacancies_tags_gin_idx on public.vacancies using gin(tags);

-- Search helper index for lightweight keyword search
create index if not exists vacancies_search_idx
on public.vacancies
using gin (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(company,'') || ' ' || coalesce(description,'')));
