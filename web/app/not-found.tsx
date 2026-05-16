import Link from "next/link";

export default function NotFound() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Job not found</h1>
      <p className="text-soft">The vacancy may have been removed or slug is invalid.</p>
      <Link href="/jobs" className="link">
        Back to jobs
      </Link>
    </section>
  );
}
