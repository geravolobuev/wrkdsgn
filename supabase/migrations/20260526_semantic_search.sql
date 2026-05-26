create table if not exists public.vacancy_embeddings (
  vacancy_id bigint primary key references public.vacancies(id) on delete cascade,
  embedding_model text not null,
  embedding double precision[] not null,
  source_text text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists vacancy_embeddings_model_idx
  on public.vacancy_embeddings (embedding_model);

create or replace function public.cosine_similarity(
  a double precision[],
  b double precision[]
) returns double precision
language sql
immutable
as $$
  select
    case
      when array_length(a, 1) is null
        or array_length(b, 1) is null
        or array_length(a, 1) <> array_length(b, 1)
      then null
      else (
        select sum(x * y) / nullif(sqrt(sum(x * x)) * sqrt(sum(y * y)), 0)
        from unnest(a, b) as t(x, y)
      )
    end
$$;

create or replace function public.semantic_search_vacancies(
  query_embedding double precision[],
  query_model text,
  limit_count integer default 30
)
returns table (
  vacancy_id bigint,
  similarity double precision
)
language sql
stable
as $$
  select
    ve.vacancy_id,
    public.cosine_similarity(ve.embedding, query_embedding) as similarity
  from public.vacancy_embeddings ve
  where ve.embedding_model = query_model
  order by similarity desc nulls last
  limit greatest(limit_count, 1)
$$;

