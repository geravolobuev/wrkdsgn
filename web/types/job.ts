export type Seniority = "Junior" | "Middle" | "Senior" | "Lead" | "Head / Director" | "Unknown" | null;

export interface Job {
  id: number;
  title: string | null;
  canonical_title: string | null;
  display_title: string | null;
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
  work_format: "Remote" | "Hybrid" | "On-site" | "Unknown" | null;
  employment_type: "Full-time" | "Part-time" | "Contract" | "Freelance" | "Internship" | "Unknown" | null;
  seniority: Seniority;
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
