-- Final strict prune for current MVP contract.
-- Keeps only fields used by current pipeline + UI/API.

alter table public.vacancies
  drop column if exists company,
  drop column if exists salary,
  drop column if exists stack,
  drop column if exists contact,
  drop column if exists reposted_at,
  drop column if exists level,
  drop column if exists raw_title;

-- Redundant: content_hash is already globally unique.
drop index if exists vacancies_source_channel_message_hash_key;
