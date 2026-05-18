export type Seniority = "Intern" | "Junior" | "Middle" | "Senior" | "Lead" | "Head" | null;

export interface Job {
  id: number;
  title: string | null;
  canonical_title: string | null;
  display_title: string | null;
  company: string | null;
  company_name: string | null;
  company_type: string | null;
  location: string | null;
  description: string | null;
  source_channel: string;
  source_link: string | null;
  created_at: string;
  published_at: string | null;
  slug: string;

  country: string | null;
  city: string | null;
  work_format: "Remote" | "Hybrid" | "Onsite" | null;
  employment_type: "Full-time" | "Part-time" | "Project" | null;
  seniority: Seniority;
  system_tags: string[] | null;
  ai_keywords: string[] | null;
  industry: string | null;
  confidence_score: number | null;
  salary_min: number | null;
  salary_max: number | null;
}

export interface JobsFilters {
  q?: string;
  specialization?: string;
  seniority?: string;
  city?: string;
  country?: string;
  work_format?: string;
  employment_type?: string;
}
