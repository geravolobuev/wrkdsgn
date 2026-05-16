import { JobCard } from "@/components/job-card";
import { JobsFiltersForm } from "@/components/jobs-filters";
import { JobsPagination } from "@/components/jobs-pagination";
import { getJobs } from "@/lib/jobs";
import type { JobsFilters } from "@/types/job";

export const revalidate = 60;

export default async function JobsPage({
  searchParams
}: {
  searchParams: { q?: string; tag?: string; remote?: "true" | "false"; seniority?: string; page?: string };
}) {
  const filters: JobsFilters = {
    q: searchParams.q,
    tag: searchParams.tag,
    remote: searchParams.remote,
    seniority: searchParams.seniority,
    page: searchParams.page
  };

  const { jobs, page, hasMore } = await getJobs(filters);

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs Feed</h1>
        <p className="text-sm text-soft">Filtered design vacancies from Telegram channels.</p>
      </div>

      <JobsFiltersForm filters={filters} />

      <div className="space-y-3">
        {jobs.length === 0 ? <p className="text-sm text-soft">No jobs found for selected filters.</p> : null}
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>

      <JobsPagination page={page} hasMore={hasMore} filters={filters} />
    </section>
  );
}
