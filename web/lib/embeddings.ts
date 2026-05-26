const OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings";
const PRIMARY_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free";
const FALLBACK_MODEL = "nomic-ai/nomic-embed-text-v1.5";

function models(): string[] {
  const p = (process.env.EMBEDDING_MODEL_PRIMARY || PRIMARY_MODEL).trim() || PRIMARY_MODEL;
  const f = (process.env.EMBEDDING_MODEL_FALLBACK || FALLBACK_MODEL).trim() || FALLBACK_MODEL;
  return p === f ? [p] : [p, f];
}

export async function getQueryEmbedding(input: string): Promise<{ embedding: number[]; model: string } | null> {
  const apiKey = (process.env.OPENROUTER_API_KEY || "").trim();
  if (!apiKey) return null;

  const text = input.slice(0, Number(process.env.EMBEDDING_TEXT_MAX_CHARS || 2500));
  const timeoutMs = Number(process.env.EMBEDDING_TIMEOUT_MS || 15000);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    for (const model of models()) {
      const response = await fetch(OPENROUTER_EMBEDDINGS_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          input: text,
          encoding_format: "float",
        }),
        signal: controller.signal,
      });

      if (!response.ok) continue;
      const json = (await response.json()) as { data?: Array<{ embedding?: number[] }> };
      const emb = json.data?.[0]?.embedding;
      if (!Array.isArray(emb) || emb.length === 0) continue;
      if (!emb.every((x) => typeof x === "number")) continue;
      return { embedding: emb, model };
    }
    return null;
  } finally {
    clearTimeout(timer);
  }
}

