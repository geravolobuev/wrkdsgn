type SearchJob = {
  id: number;
  title: string | null;
  canonical_title: string | null;
  description: string | null;
  work_format: string | null;
  employment_type: string | null;
  seniority: string | null;
  source_channel: string;
};

function extractJsonObject(text: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    // continue
  }

  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (fenced?.[1]) {
    try {
      const parsed = JSON.parse(fenced[1]);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      // continue
    }
  }

  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start >= 0 && end > start) {
    try {
      const parsed = JSON.parse(text.slice(start, end + 1));
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }
  return null;
}

export async function rerankByIntent(query: string, jobs: SearchJob[]): Promise<{
  orderedIds: number[] | null;
  intentSummary: string | null;
  reason: string | null;
  scored: Array<{ id: number; score: number; explanation: string; isRelevant: boolean }> | null;
}> {
  const apiKey = (process.env.OPENROUTER_API_KEY || "").trim();
  if (!apiKey || jobs.length === 0) {
    return { orderedIds: null, intentSummary: null, reason: "missing_api_key_or_jobs", scored: null };
  }

  const model = (process.env.OPENROUTER_SEARCH_MODEL || "openai/gpt-oss-120b:free").trim();
  const topN = Math.min(jobs.length, Number(process.env.SEARCH_RERANK_TOP_N || "80"));
  const shortlist = jobs.slice(0, topN).map((j) => ({
    id: j.id,
    role: j.canonical_title || j.title || "",
    seniority: j.seniority || "",
    work_format: j.work_format || "",
    employment_type: j.employment_type || "",
    source_channel: j.source_channel,
    description: (j.description || "").slice(0, 700),
  }));

  const prompt = [
    "You are a strict job search reranker.",
    "Understand user intent deeply (career transition, leadership intent, role target, level, format).",
    "Rank jobs by how well they match intent. Do not use keyword-only logic.",
    "If user intent implies leadership/management, individual contributor roles must get low scores unless responsibilities clearly include team leadership.",
    "If role family does not match user goal, score it low.",
    "Return ONLY JSON with fields:",
    `{"intent_summary":"...", "ordered_ids":[...], "scored":[{"id":123,"score":0-100,"is_relevant":true|false,"explanation":"..."}], "reason":"..."}`,
    "ordered_ids must contain only ids from given candidates, best-to-worst.",
    "scored must include only ids from candidates.",
    "explanation must be short and concrete (1 sentence).",
    "",
    `USER_QUERY: ${query}`,
    `CANDIDATES: ${JSON.stringify(shortlist)}`,
  ].join("\n");

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        temperature: 0,
        max_tokens: 700,
        messages: [
          { role: "system", content: "Return strict JSON only." },
          { role: "user", content: prompt },
        ],
      }),
    });
    if (!response.ok) {
      return { orderedIds: null, intentSummary: null, reason: `api_error_${response.status}`, scored: null };
    }
    const json = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = json.choices?.[0]?.message?.content;
    if (!content) {
      return { orderedIds: null, intentSummary: null, reason: "empty_content", scored: null };
    }
    const parsed = extractJsonObject(content);
    if (!parsed) {
      return { orderedIds: null, intentSummary: null, reason: "invalid_json", scored: null };
    }
    const ids = Array.isArray(parsed.ordered_ids)
      ? parsed.ordered_ids.filter((v): v is number => typeof v === "number")
      : [];
    const allowed = new Set(shortlist.map((x) => x.id));
    const orderedIds = ids.filter((id) => allowed.has(id));
    if (orderedIds.length === 0) {
      return { orderedIds: null, intentSummary: null, reason: "empty_ordered_ids", scored: null };
    }
    const scoredRaw = Array.isArray(parsed.scored) ? parsed.scored : [];
    let scored = scoredRaw
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const id = (item as Record<string, unknown>).id;
        const score = (item as Record<string, unknown>).score;
        const isRelevant = (item as Record<string, unknown>).is_relevant;
        const explanation = (item as Record<string, unknown>).explanation;
        if (typeof id !== "number" || typeof score !== "number" || typeof explanation !== "string") return null;
        if (!allowed.has(id)) return null;
        return {
          id,
          score: Math.max(0, Math.min(100, score)),
          isRelevant: typeof isRelevant === "boolean" ? isRelevant : score >= 60,
          explanation: explanation.slice(0, 220),
        };
      })
      .filter((x): x is { id: number; score: number; explanation: string; isRelevant: boolean } => Boolean(x));

    if (!scored.length) {
      const max = Math.max(orderedIds.length, 1);
      scored = orderedIds.map((id, idx) => {
        const score = Math.max(5, Math.round(100 - (idx * 100) / max));
        return {
          id,
          score,
          isRelevant: idx < Math.min(10, Math.ceil(max * 0.4)),
          explanation: "Matched by AI intent reranking.",
        };
      });
    }
    return {
      orderedIds,
      intentSummary: typeof parsed.intent_summary === "string" ? parsed.intent_summary.slice(0, 200) : null,
      reason: typeof parsed.reason === "string" ? parsed.reason.slice(0, 300) : null,
      scored: scored.length ? scored : null,
    };
  } catch {
    return { orderedIds: null, intentSummary: null, reason: "request_failed", scored: null };
  }
}
