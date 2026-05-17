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
  const level = (searchParams.get("level") || "").trim();
  const city = (searchParams.get("city") || "").trim();
  const country = (searchParams.get("country") || "").trim();
  const remoteType = (searchParams.get("remote_type") || "").trim();
  const employmentType = (searchParams.get("employment_type") || "").trim();

  let query = supabase
    .from("vacancies")
    .select(
      "id,title,company,location,description,source_channel,source_link,created_at,published_at,slug,country,city,remote_type,employment_type,level,role_type,specializations,semantic_tags,tools,language,salary_min,salary_max",
      { count: "exact" }
    )
    .eq("is_job", true)
    .order("published_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .range(from, to);

  if (q) {
    query = query.or(`title.ilike.%${q}%,company.ilike.%${q}%,description.ilike.%${q}%,city.ilike.%${q}%,country.ilike.%${q}%`);
  }

  if (specialization) {
    query = query.contains("specializations", [specialization]);
  }

  if (level) {
    query = query.eq("level", level);
  }

  if (city) {
    query = query.ilike("city", `%${city}%`);
  }

  if (country) {
    query = query.ilike("country", `%${country}%`);
  }

  if (remoteType) {
    query = query.eq("remote_type", remoteType);
  }

  if (employmentType) {
    query = query.eq("employment_type", employmentType);
  }

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const jobs = data || [];
  const hasMore = typeof count === "number" ? to + 1 < count : jobs.length === PAGE_SIZE;

  return NextResponse.json({ jobs, page: safePage, hasMore });
}
