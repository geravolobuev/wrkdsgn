export type Seniority = "Junior" | "Middle" | "Senior" | "Lead" | "Head / Director" | "Unknown" | null;

export interface Job {
  id: number;
  title: string | null;
  canonical_title: string | null;
  display_title: string | null;
  description: string | null;
  source_channel: string;
  source_link: string | null;
  created_at: string;
  published_at: string | null;
  slug: string;
  employment_type: "Full-time" | "Part-time" | "Contract" | "Freelance" | "Internship" | "Unknown" | null;
  seniority: Seniority;
  work_format: "Remote" | "Hybrid" | "On-site" | "Unknown" | null;
}

export interface JobsFilters {
  q?: string;
  specialization?: string;
  seniority?: string;
  work_format?: string;
  employment_type?: string;
}
