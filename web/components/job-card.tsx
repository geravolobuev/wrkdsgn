import Link from "next/link";

import { formatRelativeDate } from "@/lib/time";
import type { Job } from "@/types/job";

export function JobCard({ job }: { job: Job }) {
  const excerpt = (job.description || "").slice(0, 190);

  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">
            <Link href={`/jobs/${job.slug}`} className="hover:underline">
              {job.title || "Untitled Vacancy"}
            </Link>
          </h3>
          <p className="text-sm text-soft">
            {job.company || "Unknown company"} · {job.location || "Location not specified"}
          </p>
        </div>
        <time className="shrink-0 text-xs text-soft">{formatRelativeDate(job.created_at)}</time>
      </div>

      <p className="mb-3 text-sm text-soft">{excerpt}{excerpt.length >= 190 ? "..." : ""}</p>

      <div className="flex flex-wrap items-center gap-2">
        {job.remote ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">remote</span> : null}
        {job.seniority ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.seniority}</span> : null}
        {(job.tags || []).slice(0, 4).map((tag) => (
          <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-soft">
            {tag}
          </span>
        ))}
      </div>
    </article>
  );
}
