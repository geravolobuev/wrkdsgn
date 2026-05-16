import Link from "next/link";

export default function HomePage() {
  return (
    <section className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Design jobs, not noise.</h1>
      <p className="max-w-2xl text-soft">
        A minimal feed of design vacancies aggregated from selected Telegram channels. No accounts, no clutter.
      </p>
      <Link
        href="/jobs"
        className="inline-flex rounded-md border border-ink bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Browse Jobs
      </Link>
    </section>
  );
}
