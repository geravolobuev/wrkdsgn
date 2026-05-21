import { supabase } from "@/lib/supabase";
import type { Job } from "@/types/job";

export async function getJobBySlug(slug: string): Promise<Job | null> {
  const { data, error } = await supabase
    .from("vacancies")
    .select(
      "id,title,canonical_title,display_title,description,source_channel,source_link,created_at,published_at,slug,work_format,employment_type,seniority"
    )
    .eq("slug", slug)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  return (data as Job | null) || null;
}
