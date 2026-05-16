export type Seniority = "junior" | "middle" | "senior" | "lead" | "intern" | null;

export interface Job {
  id: number;
  title: string | null;
  company: string | null;
  location: string | null;
  remote: boolean | null;
  seniority: Seniority;
  tags: string[] | null;
  description: string | null;
  source_channel: string;
  source_link: string | null;
  created_at: string;
  published_at: string | null;
  slug: string;
}

export interface JobsFilters {
  q?: string;
  tag?: string;
  remote?: "true" | "false";
  seniority?: string;
}
