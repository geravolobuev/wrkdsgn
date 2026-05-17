-- Allow multiple split jobs from same source message while preserving idempotency.

alter table public.vacancies
  drop constraint if exists vacancies_source_channel_source_message_id_key;

drop index if exists vacancies_source_channel_source_message_id_key;

create unique index if not exists vacancies_source_channel_message_hash_key
  on public.vacancies(source_channel, source_message_id, content_hash);
