import { notFound } from "next/navigation";

import { getJobBySlug } from "@/lib/jobs";
import { formatRelativeDate } from "@/lib/time";

export const revalidate = 60;

export default async function JobDetailPage({ params }: { params: { slug: string } }) {
  const job = await getJobBySlug(params.slug);

  if (!job) notFound();

  const published = job.published_at || job.created_at;

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{job.display_title || job.canonical_title || job.title || "Untitled Vacancy"}</h1>
        <p className="text-soft">{job.source_channel}</p>
        <p className="text-sm text-soft">Published {formatRelativeDate(published)}</p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {job.work_format ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.work_format}</span> : null}
        {job.seniority ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.seniority}</span> : null}
        {job.employment_type ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.employment_type}</span> : null}
        {job.canonical_title ? <span className="rounded-full border border-line px-2 py-0.5 text-xs">{job.canonical_title}</span> : null}
      </div>

      <section className="rounded-lg border border-line bg-white p-5">
        <h2 className="mb-3 text-lg font-medium">Description</h2>
        <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{job.description || "No description"}</p>
      </section>

      <section className="rounded-lg border border-line bg-white p-5 text-sm">
        <h2 className="mb-3 text-lg font-medium">Metadata</h2>
        <ul className="space-y-2 text-soft">
          <li>Role: {job.canonical_title || "n/a"}</li>
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
