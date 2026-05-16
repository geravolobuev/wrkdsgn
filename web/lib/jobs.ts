import { supabase } from "@/lib/supabase";
import type { Job, JobsFilters } from "@/types/job";

const PAGE_SIZE = 20;

export async function getJobs(filters: JobsFilters): Promise<{ jobs: Job[]; page: number; hasMore: boolean }> {
  const page = Number(filters.page || "1");
  const safePage = Number.isFinite(page) && page > 0 ? page : 1;
  const from = (safePage - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE;

  let query = supabase
    .from("vacancies")
    .select(
      "id,title,company,location,remote,seniority,tags,description,source_channel,source_link,created_at,slug",
      { count: "exact" }
    )
    .order("created_at", { ascending: false })
    .range(from, to - 1);

  if (filters.q) {
    query = query.or(`title.ilike.%${filters.q}%,company.ilike.%${filters.q}%,description.ilike.%${filters.q}%`);
  }

  if (filters.tag) {
    query = query.contains("tags", [filters.tag]);
  }

  if (filters.remote === "true") {
    query = query.eq("remote", true);
  }

  if (filters.seniority) {
    query = query.eq("seniority", filters.seniority);
  }

  const { data, error, count } = await query;

  if (error) {
    throw new Error(error.message);
  }

  const jobs = (data || []) as Job[];
  const hasMore = typeof count === "number" ? to < count : jobs.length === PAGE_SIZE;

  return { jobs, page: safePage, hasMore };
}

export async function getJobBySlug(slug: string): Promise<Job | null> {
  const { data, error } = await supabase
    .from("vacancies")
    .select("id,title,company,location,remote,seniority,tags,description,source_channel,source_link,created_at,slug")
    .eq("slug", slug)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  return (data as Job | null) || null;
}
