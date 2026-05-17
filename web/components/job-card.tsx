"use client";

import { formatRelativeDate } from "@/lib/time";
import type { Job } from "@/types/job";

function salaryLabel(job: Job): string | null {
  if (job.salary_min === null && job.salary_max === null) return null;
  if (job.salary_min !== null && job.salary_max !== null) return `${job.salary_min} - ${job.salary_max}`;
  if (job.salary_min !== null) return `from ${job.salary_min}`;
  return `up to ${job.salary_max}`;
}

export function JobCard({
  job,
  isOpen,
  onToggle,
}: {
  job: Job;
  isOpen: boolean;
  onToggle: (id: number) => void;
}) {
  const excerpt = (job.description || "").slice(0, 180);
  const published = job.published_at || job.created_at;
  const salary = salaryLabel(job);

  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5">
      <button className="w-full text-left" onClick={() => onToggle(job.id)} type="button">
        <div className="mb-2 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">{job.title || "Untitled Vacancy"}</h3>
            <p className="text-sm text-soft">
              {job.company || "Unknown company"}
              {job.city || job.country ? ` · ${job.city || ""}${job.city && job.country ? ", " : ""}${job.country || ""}` : ""}
            </p>
          </div>
          <time className="shrink-0 text-xs text-soft">{formatRelativeDate(published)}</time>
        </div>
        <p className="text-sm text-soft">{excerpt}{excerpt.length >= 180 ? "..." : ""}</p>
      </button>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {job.remote_type ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.remote_type}</span> : null}
        {job.level ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.level}</span> : null}
        {job.employment_type ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.employment_type}</span> : null}
        {(job.specializations || []).slice(0, 4).map((tag) => (
          <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-soft">
            {tag}
          </span>
        ))}
      </div>

      {isOpen ? (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          <p className="whitespace-pre-wrap text-sm leading-6">{job.description || "No description"}</p>
          <div className="grid gap-2 text-sm text-soft sm:grid-cols-2">
            <span>Country: {job.country || "n/a"}</span>
            <span>City: {job.city || "n/a"}</span>
            <span>Role type: {job.role_type || "n/a"}</span>
            <span>Salary: {salary || "n/a"}</span>
          </div>
          {(job.semantic_tags || []).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {(job.semantic_tags || []).map((tag) => (
                <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-soft">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
          {job.source_link ? (
            <a className="link text-sm" href={job.source_link} rel="noreferrer" target="_blank">
              Open original post
            </a>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
