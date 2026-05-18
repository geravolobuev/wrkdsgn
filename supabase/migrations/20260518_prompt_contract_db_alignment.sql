-- Align DB constraints and values with new AI prompt contract.

-- 1) employment_type now uses prompt values:
-- Full-time | Part-time | Contract | Freelance | Internship | Unknown
alter table public.vacancies
  drop constraint if exists vacancies_employment_type_check;

update public.vacancies
set employment_type = case employment_type
  when 'full_time' then 'Full-time'
  when 'part_time' then 'Part-time'
  when 'contract' then 'Contract'
  when 'freelance' then 'Freelance'
  when 'internship' then 'Internship'
  else employment_type
end
where employment_type is not null;

alter table public.vacancies
  add constraint vacancies_employment_type_check
  check (
    employment_type is null
    or employment_type in ('Full-time','Part-time','Contract','Freelance','Internship','Unknown')
  );

-- 2) Add optional constraints for new normalized fields
alter table public.vacancies
  drop constraint if exists vacancies_work_format_check;
alter table public.vacancies
  add constraint vacancies_work_format_check
  check (
    work_format is null
    or work_format in ('Remote','Hybrid','On-site','Unknown')
  );

alter table public.vacancies
  drop constraint if exists vacancies_seniority_check;
alter table public.vacancies
  add constraint vacancies_seniority_check
  check (
    seniority is null
    or seniority in ('Junior','Middle','Senior','Lead','Head / Director','Unknown')
  );

-- 3) Indexes for current filters
create index if not exists vacancies_canonical_title_idx on public.vacancies(canonical_title);
create index if not exists vacancies_seniority_v2_idx on public.vacancies(seniority);
create index if not exists vacancies_work_format_idx on public.vacancies(work_format);
create index if not exists vacancies_employment_type_v2_idx on public.vacancies(employment_type);
