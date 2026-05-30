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
}> {
  const apiKey = (process.env.OPENROUTER_API_KEY || "").trim();
  if (!apiKey || jobs.length === 0) {
    return { orderedIds: null, intentSummary: null, reason: "missing_api_key_or_jobs" };
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
    "Return ONLY JSON with fields:",
    `{"intent_summary":"...", "ordered_ids":[...], "reason":"..."}`,
    "ordered_ids must contain only ids from given candidates, best-to-worst.",
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
      return { orderedIds: null, intentSummary: null, reason: `api_error_${response.status}` };
    }
    const json = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const content = json.choices?.[0]?.message?.content;
    if (!content) {
      return { orderedIds: null, intentSummary: null, reason: "empty_content" };
    }
    const parsed = extractJsonObject(content);
    if (!parsed) {
      return { orderedIds: null, intentSummary: null, reason: "invalid_json" };
    }
    const ids = Array.isArray(parsed.ordered_ids)
      ? parsed.ordered_ids.filter((v): v is number => typeof v === "number")
      : [];
    const allowed = new Set(shortlist.map((x) => x.id));
    const orderedIds = ids.filter((id) => allowed.has(id));
    if (orderedIds.length === 0) {
      return { orderedIds: null, intentSummary: null, reason: "empty_ordered_ids" };
    }
    return {
      orderedIds,
      intentSummary: typeof parsed.intent_summary === "string" ? parsed.intent_summary.slice(0, 200) : null,
      reason: typeof parsed.reason === "string" ? parsed.reason.slice(0, 200) : null,
    };
  } catch {
    return { orderedIds: null, intentSummary: null, reason: "request_failed" };
  }
}

