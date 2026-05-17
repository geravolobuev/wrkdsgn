import { supabase } from "@/lib/supabase";
import type { Job } from "@/types/job";

export async function getJobBySlug(slug: string): Promise<Job | null> {
  const { data, error } = await supabase
    .from("vacancies")
    .select(
      "id,title,company,location,description,source_channel,source_link,created_at,published_at,slug,country,city,remote_type,employment_type,level,role_type,specializations,semantic_tags,tools,language,salary_min,salary_max"
    )
    .eq("slug", slug)
    .limit(1)
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  return (data as Job | null) || null;
}
