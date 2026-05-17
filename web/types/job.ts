export type Level = "intern" | "junior" | "middle" | "senior" | "lead" | "head" | "director" | null;

export interface Job {
  id: number;
  title: string | null;
  company: string | null;
  location: string | null;
  description: string | null;
  source_channel: string;
  source_link: string | null;
  created_at: string;
  published_at: string | null;
  slug: string;

  country: string | null;
  city: string | null;
  remote_type: "remote" | "hybrid" | "onsite" | null;
  employment_type: "full_time" | "part_time" | "contract" | "freelance" | "internship" | null;
  level: Level;
  role_type: string | null;
  specializations: string[] | null;
  semantic_tags: string[] | null;
  tools: string[] | null;
  language: string[] | null;
  salary_min: number | null;
  salary_max: number | null;
}

export interface JobsFilters {
  q?: string;
  specialization?: string;
  level?: string;
  city?: string;
  country?: string;
  remote_type?: string;
  employment_type?: string;
}
