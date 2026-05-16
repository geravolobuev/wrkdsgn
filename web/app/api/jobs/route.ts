import { NextRequest, NextResponse } from "next/server";

import { supabase } from "@/lib/supabase";

const PAGE_SIZE = 20;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const page = Number(searchParams.get("page") || "1");
  const safePage = Number.isFinite(page) && page > 0 ? page : 1;
  const from = (safePage - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  const q = (searchParams.get("q") || "").trim();
  const tag = (searchParams.get("tag") || "").trim();
  const remote = (searchParams.get("remote") || "").trim();
  const seniority = (searchParams.get("seniority") || "").trim();

  let query = supabase
    .from("vacancies")
    .select(
      "id,title,company,location,remote,seniority,tags,description,source_channel,source_link,created_at,published_at,slug",
      { count: "exact" }
    )
    .order("published_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .range(from, to);

  if (q) {
    query = query.or(`title.ilike.%${q}%,company.ilike.%${q}%,description.ilike.%${q}%`);
  }

  if (tag) {
    query = query.contains("tags", [tag]);
  }

  if (remote === "true") {
    query = query.eq("remote", true);
  }

  if (seniority) {
    query = query.eq("seniority", seniority);
  }

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const jobs = data || [];
  const hasMore = typeof count === "number" ? to + 1 < count : jobs.length === PAGE_SIZE;

  return NextResponse.json({ jobs, page: safePage, hasMore });
}
