-- 1) Remove already duplicated rows by dedupe_key, keep the earliest record.
with ranked as (
  select
    id,
    dedupe_key,
    row_number() over (partition by dedupe_key order by id asc) as rn
  from public.vacancies
  where dedupe_key is not null
)
delete from public.vacancies v
using ranked r
where v.id = r.id
  and r.rn > 1;

-- 2) Enforce uniqueness for future inserts.
create unique index if not exists vacancies_dedupe_key_unique_idx
  on public.vacancies (dedupe_key)
  where dedupe_key is not null;

