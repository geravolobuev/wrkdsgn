import { NextRequest, NextResponse } from "next/server";

import { getQueryEmbedding } from "@/lib/embeddings";
import { expandSearchIntent, rerankByIntent } from "@/lib/search-intent";
import { supabase } from "@/lib/supabase";

const PAGE_SIZE = 20;
const DEFAULT_MIN_RELEVANCE = 60;

type JobRow = {
  id: number;
  title: string | null;
  canonical_title: string | null;
  display_title: string | null;
  description: string | null;
  source_channel: string;
  source_link: string | null;
  created_at: string;
  published_at: string | null;
  slug: string | null;
  work_format: string | null;
  employment_type: string | null;
  seniority: string | null;
};

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
  const effectiveSpecialization = specialization || "";

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
  const rerankEnabled = (process.env.ENABLE_AI_RERANK || "true").toLowerCase() === "true";
  const intentExpansionEnabled = (process.env.ENABLE_AI_QUERY_EXPANSION || "true").toLowerCase() === "true";
  const expandedQueries = q && intentExpansionEnabled ? (await expandSearchIntent(q)).expandedQueries : [];
  const retrievalQueries = [q, ...expandedQueries].map((x) => x.trim()).filter(Boolean).slice(0, 8);
  if (q) debug.ai_rerank_enabled = rerankEnabled;
  if (q) debug.ai_query_expansion_enabled = intentExpansionEnabled;
  if (expandedQueries.length) debug.expanded_queries = expandedQueries.length;

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
        const semanticIds = semRows.map((row: { vacancy_id: number }) => row.vacancy_id).filter(Boolean);
        let textIds: number[] = [];

        if (retrievalQueries.length > 0) {
          const orParts = retrievalQueries.flatMap((rq) => [
            `title.ilike.%${rq}%`,
            `canonical_title.ilike.%${rq}%`,
            `description.ilike.%${rq}%`,
          ]);
          const { data: textRows, error: textErr } = await supabase
            .from("vacancies")
            .select("id")
            .eq("is_job", true)
            .or(orParts.join(","))
            .limit(500);
          if (!textErr && textRows) {
            textIds = textRows.map((r: { id: number }) => r.id).filter(Boolean);
            debug.text_match_candidates = textIds.length;
          }
        }

        const ids = [...textIds, ...semanticIds.filter((id: number) => !textIds.includes(id))];
        if (ids.length > 0) {
          let semQuery = supabase.from("vacancies").select(baseSelect).eq("is_job", true).in("id", ids);
          if (effectiveSpecialization) semQuery = semQuery.eq("canonical_title", effectiveSpecialization);
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
            let ordered = [...semJobs].sort(
              (a: JobRow, b: JobRow) => (rank.get(a.id) ?? 10_000) - (rank.get(b.id) ?? 10_000)
            );

            if (q && rerankEnabled) {
              const rerank = await rerankByIntent(q, ordered);
              if (rerank.orderedIds) {
                const rr = new Map<number, number>();
                rerank.orderedIds.forEach((id: number, idx: number) => rr.set(id, idx));
                ordered = [...ordered].sort(
                  (a: JobRow, b: JobRow) => (rr.get(a.id) ?? 10_000) - (rr.get(b.id) ?? 10_000)
                );
                debug.rerank_reason = rerank.reason || "ok";
                if (rerank.intentSummary) debug.intent_summary = rerank.intentSummary;

                if (rerank.scored?.length) {
                  const scoredMap = new Map<number, { score: number; explanation: string; isRelevant: boolean }>();
                  rerank.scored.forEach((r) =>
                    scoredMap.set(r.id, { score: r.score, explanation: r.explanation, isRelevant: r.isRelevant })
                  );

                  const thresholdRaw = Number(process.env.SEARCH_MIN_RELEVANCE_SCORE || `${DEFAULT_MIN_RELEVANCE}`);
                  const threshold = Number.isFinite(thresholdRaw) ? thresholdRaw : DEFAULT_MIN_RELEVANCE;
                  debug.min_relevance_score = threshold;

                  const relevantOnly = ordered.filter((job: JobRow) => scoredMap.get(job.id)?.isRelevant === true);
                  const byScore = relevantOnly.filter(
                    (job: JobRow) => (scoredMap.get(job.id)?.score ?? 0) >= threshold
                  );
                  const filtered = byScore.length > 0 ? byScore : relevantOnly;
                  if (filtered.length > 0) {
                    ordered = filtered;
                    debug.relevance_filter = "applied";
                  } else {
                    debug.relevance_filter = "skipped_empty_after_filter";
                  }

                  // Keep query expansion text matches in recall even after strict relevance filtering.
                  if (textIds.length > 0) {
                    const textSet = new Set(textIds);
                    const textBackfill = semJobs.filter(
                      (j: JobRow) => textSet.has(j.id) && !ordered.some((x: JobRow) => x.id === j.id)
                    );
                    if (textBackfill.length) {
                      ordered = [...ordered, ...textBackfill];
                      debug.text_backfill = textBackfill.length;
                    }
                  }

                  ordered = ordered.map((job: JobRow) => {
                    const scored = scoredMap.get(job.id);
                    return {
                      ...job,
                      relevance_score: scored?.score ?? null,
                      relevance_explanation: scored?.explanation ?? null,
                    };
                  });
                }
              } else {
                debug.rerank_reason = rerank.reason || "rerank_unavailable";
              }
            }

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

  if (q) {
    const fallbackQueries = retrievalQueries.length > 0 ? retrievalQueries : [q];
    const orParts = fallbackQueries.flatMap((rq) => [
      `title.ilike.%${rq}%`,
      `canonical_title.ilike.%${rq}%`,
      `description.ilike.%${rq}%`,
    ]);
    query = query.or(orParts.join(","));
  }

  if (effectiveSpecialization) query = query.eq("canonical_title", effectiveSpecialization);
  if (seniority) query = query.eq("seniority", seniority);
  if (workFormat) query = query.eq("work_format", workFormat);
  if (employmentType) query = query.eq("employment_type", employmentType);

  const { data, error, count } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const jobs = data || [];
  const hasMore = typeof count === "number" ? to + 1 < count : jobs.length === PAGE_SIZE;
  return NextResponse.json({ jobs, page: safePage, hasMore, mode, debug });
}
