import { NextRequest, NextResponse } from "next/server";

import { getQueryEmbedding } from "@/lib/embeddings";
import { supabase } from "@/lib/supabase";

const PAGE_SIZE = 20;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const page = Number(searchParams.get("page") || "1");
  const safePage = Number.isFinite(page) && page > 0 ? page : 1;
  const from = (safePage - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  const q = (searchParams.get("q") || "").trim();
  const specialization = (searchParams.get("specialization") || "").trim();
  const seniority = (searchParams.get("seniority") || "").trim();
  const workFormat = (searchParams.get("work_format") || "").trim();
  const employmentType = (searchParams.get("employment_type") || "").trim();

  const baseSelect =
    "id,title,canonical_title,display_title,description,source_channel,source_link,created_at,published_at,slug,work_format,employment_type,seniority";

  let query = supabase
    .from("vacancies")
    .select(baseSelect, { count: "exact" })
    .eq("is_job", true)
    .order("published_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .range(from, to);

  const semanticEnabled = (process.env.ENABLE_SEMANTIC_SEARCH || "false").toLowerCase() === "true";
  let mode: "semantic" | "fallback_text" = "fallback_text";
  const debug: Record<string, string | number | boolean> = {
    semantic_enabled: semanticEnabled,
  };

  if (q && semanticEnabled) {
    const embeddingResult = await getQueryEmbedding(q);
    if (!embeddingResult) {
      debug.semantic_reason = "embedding_unavailable";
    }
    if (embeddingResult) {
      debug.embedding_model = embeddingResult.model;
      const { data: semRows, error: semErr } = await supabase.rpc("semantic_search_vacancies", {
        query_embedding: embeddingResult.embedding,
        query_model: embeddingResult.model,
        limit_count: 200,
      });
      if (semErr) {
        debug.semantic_reason = "rpc_error";
      }
      if (!semErr && semRows && semRows.length > 0) {
        debug.semantic_candidates = semRows.length;
        const ids = semRows.map((row: { vacancy_id: number }) => row.vacancy_id).filter(Boolean);
        if (ids.length > 0) {
          let semQuery = supabase.from("vacancies").select(baseSelect).eq("is_job", true).in("id", ids);
          if (specialization) semQuery = semQuery.eq("canonical_title", specialization);
          if (seniority) semQuery = semQuery.eq("seniority", seniority);
          if (workFormat) semQuery = semQuery.eq("work_format", workFormat);
          if (employmentType) semQuery = semQuery.eq("employment_type", employmentType);

          const { data: semJobs, error: semJobsErr } = await semQuery;
          if (semJobsErr) {
            debug.semantic_reason = "semantic_select_error";
          }
          if (!semJobsErr && semJobs) {
            const rank = new Map<number, number>();
            ids.forEach((id: number, idx: number) => rank.set(id, idx));
            const ordered = [...semJobs].sort((a, b) => (rank.get(a.id) ?? 10_000) - (rank.get(b.id) ?? 10_000));
            const start = from;
            const end = to + 1;
            const jobs = ordered.slice(start, end);
            const hasMore = ordered.length > end;
            mode = "semantic";
            return NextResponse.json({ jobs, page: safePage, hasMore, mode, debug });
          }
        }
      } else if (!semErr) {
        debug.semantic_reason = "no_semantic_rows";
      }
    }
  } else if (q) {
    debug.semantic_reason = semanticEnabled ? "no_query" : "semantic_disabled";
  }

  if (q) query = query.or(`title.ilike.%${q}%,canonical_title.ilike.%${q}%,description.ilike.%${q}%`);

  if (specialization) query = query.eq("canonical_title", specialization);
  if (seniority) query = query.eq("seniority", seniority);
  if (workFormat) query = query.eq("work_format", workFormat);
  if (employmentType) query = query.eq("employment_type", employmentType);

  const { data, error, count } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const jobs = data || [];
  const hasMore = typeof count === "number" ? to + 1 < count : jobs.length === PAGE_SIZE;
  return NextResponse.json({ jobs, page: safePage, hasMore, mode, debug });
}
