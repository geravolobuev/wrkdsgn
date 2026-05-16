"use client";

import { formatRelativeDate } from "@/lib/time";
import type { Job } from "@/types/job";

function deriveSeniority(job: Job): string | null {
  if (job.seniority) return job.seniority;
  const text = `${job.title || ""} ${job.description || ""}`.toLowerCase();
  if (/(junior|джун)/.test(text)) return "junior";
  if (/(middle|mid|мидл|мид)/.test(text)) return "middle";
  if (/(senior|сеньор)/.test(text)) return "senior";
  if (/(lead|тимлид)/.test(text)) return "lead";
  if (/(intern|стаж)/.test(text)) return "intern";
  return null;
}

function deriveTags(job: Job): string[] {
  if (job.tags && job.tags.length > 0) return job.tags;
  const text = `${job.title || ""} ${job.description || ""}`.toLowerCase();
  const tags: string[] = [];
  const map: Record<string, RegExp> = {
    ux: /\bux\b/,
    ui: /\bui\b/,
    product: /(product designer|продуктов)/,
    graphic: /(graphic|графическ)/,
    motion: /motion/,
    web: /(\bweb\b|веб)/,
    mobile: /(mobile|ios|android)/,
    figma: /figma/,
    freelance: /(freelance|фриланс)/
  };
  for (const [tag, re] of Object.entries(map)) {
    if (re.test(text)) tags.push(tag);
  }
  return tags;
}

export function JobCard({
  job,
  isOpen,
  onToggle
}: {
  job: Job;
  isOpen: boolean;
  onToggle: (id: number) => void;
}) {
  const excerpt = (job.description || "").slice(0, 180);
  const published = job.published_at || job.created_at;
  const tags = deriveTags(job);
  const seniority = deriveSeniority(job);

  return (
    <article className="rounded-lg border border-line bg-white p-4 sm:p-5">
      <button className="w-full text-left" onClick={() => onToggle(job.id)} type="button">
        <div className="mb-2 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">{job.title || "Untitled Vacancy"}</h3>
            <p className="text-sm text-soft">
              {job.company || "Unknown company"} · {job.location || "Location not specified"}
            </p>
          </div>
          <time className="shrink-0 text-xs text-soft">{formatRelativeDate(published)}</time>
        </div>
        <p className="text-sm text-soft">{excerpt}{excerpt.length >= 180 ? "..." : ""}</p>
      </button>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {job.remote ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">remote</span> : null}
        {seniority ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{seniority}</span> : null}
        {tags.slice(0, 5).map((tag) => (
          <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-soft">
            {tag}
          </span>
        ))}
      </div>

      {isOpen ? (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          <p className="whitespace-pre-wrap text-sm leading-6">{job.description || "No description"}</p>
          <div className="flex flex-wrap gap-4 text-sm text-soft">
            <span>Source: {job.source_channel}</span>
            {job.source_link ? (
              <a className="link" href={job.source_link} rel="noreferrer" target="_blank">
                Open original post
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
