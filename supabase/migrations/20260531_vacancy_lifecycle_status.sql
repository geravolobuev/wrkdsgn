create or replace function public.compute_vacancy_status(
  published_at_ts timestamptz,
  created_at_ts timestamptz default null
)
returns text
language sql
stable
as $$
  select case
    when now() - coalesce(published_at_ts, created_at_ts, now()) <= interval '30 days' then 'active'
    when now() - coalesce(published_at_ts, created_at_ts, now()) <= interval '60 days' then 'stale'
    else 'archived'
  end
$$;

alter table public.vacancies
  add column if not exists status text;

alter table public.vacancies
  drop constraint if exists vacancies_status_check;

update public.vacancies
set status = public.compute_vacancy_status(published_at, created_at)
where status is distinct from public.compute_vacancy_status(published_at, created_at);

alter table public.vacancies
  alter column status set default 'active';

update public.vacancies
set status = public.compute_vacancy_status(published_at, created_at)
where status is null;

alter table public.vacancies
  alter column status set not null;

alter table public.vacancies
  add constraint vacancies_status_check
  check (status = any (array['active'::text, 'stale'::text, 'archived'::text]));

create index if not exists vacancies_status_idx
  on public.vacancies(status);

create index if not exists vacancies_status_published_at_idx
  on public.vacancies(status, published_at desc);

create or replace function public.set_vacancy_status_from_dates()
returns trigger
language plpgsql
as $$
begin
  new.status := public.compute_vacancy_status(new.published_at, new.created_at);
  return new;
end;
$$;

drop trigger if exists set_vacancy_status_from_dates_trigger on public.vacancies;

create trigger set_vacancy_status_from_dates_trigger
before insert or update of published_at, created_at
on public.vacancies
for each row
execute function public.set_vacancy_status_from_dates();

create or replace function public.refresh_recent_vacancy_statuses()
returns integer
language plpgsql
as $$
declare
  affected_count integer;
begin
  update public.vacancies
  set status = public.compute_vacancy_status(published_at, created_at)
  where (
    coalesce(published_at, created_at, now()) >= now() - interval '90 days'
    or status is null
  )
  and status is distinct from public.compute_vacancy_status(published_at, created_at);

  get diagnostics affected_count = row_count;
  return affected_count;
end;
$$;

select public.refresh_recent_vacancy_statuses();
