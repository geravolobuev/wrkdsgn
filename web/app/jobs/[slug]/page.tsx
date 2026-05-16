import { notFound } from "next/navigation";

import { formatRelativeDate } from "@/lib/time";
import { getJobBySlug } from "@/lib/jobs";

export const revalidate = 60;

export default async function JobDetailPage({ params }: { params: { slug: string } }) {
  const job = await getJobBySlug(params.slug);

  if (!job) {
    notFound();
  }

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{job.title || "Untitled Vacancy"}</h1>
        <p className="text-soft">
          {job.company || "Unknown company"} · {job.location || "Location not specified"}
        </p>
        <p className="text-sm text-soft">Published {formatRelativeDate(job.published_at || job.created_at)}</p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {job.remote ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">remote</span> : null}
        {job.seniority ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.seniority}</span> : null}
        {(job.tags || []).map((tag) => (
          <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs text-soft">
            {tag}
          </span>
        ))}
      </div>

      <section className="rounded-lg border border-line bg-white p-5">
        <h2 className="mb-3 text-lg font-medium">Description</h2>
        <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{job.description || "No description"}</p>
      </section>

      <section className="rounded-lg border border-line bg-white p-5 text-sm">
        <h2 className="mb-3 text-lg font-medium">Metadata</h2>
        <ul className="space-y-2 text-soft">
          <li>Source channel: {job.source_channel}</li>
          <li>
            Source link:{" "}
            {job.source_link ? (
              <a className="link" href={job.source_link} rel="noreferrer" target="_blank">
                Open original post
              </a>
            ) : (
              "not available"
            )}
          </li>
        </ul>
      </section>
    </article>
  );
}
