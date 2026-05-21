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
  const specialization = (searchParams.get("specialization") || "").trim();
  const seniority = (searchParams.get("seniority") || "").trim();
  const workFormat = (searchParams.get("work_format") || "").trim();
  const employmentType = (searchParams.get("employment_type") || "").trim();

  let query = supabase
    .from("vacancies")
    .select(
      "id,title,canonical_title,display_title,description,source_channel,source_link,created_at,published_at,slug,work_format,employment_type,seniority",
      { count: "exact" }
    )
    .eq("is_job", true)
    .order("published_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .range(from, to);

  if (q) {
    query = query.or(`title.ilike.%${q}%,canonical_title.ilike.%${q}%,description.ilike.%${q}%`);
  }

  if (specialization) query = query.eq("canonical_title", specialization);
  if (seniority) query = query.eq("seniority", seniority);
  if (workFormat) query = query.eq("work_format", workFormat);
  if (employmentType) query = query.eq("employment_type", employmentType);

  const { data, error, count } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const jobs = data || [];
  const hasMore = typeof count === "number" ? to + 1 < count : jobs.length === PAGE_SIZE;
  return NextResponse.json({ jobs, page: safePage, hasMore });
}
