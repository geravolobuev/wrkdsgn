"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { JobCard } from "@/components/job-card";
import type { Job } from "@/types/job";

const TAG_OPTIONS = ["", "ux", "ui", "product", "graphic", "motion", "brand", "web", "mobile", "figma", "freelance"];
const SENIORITY_OPTIONS = ["", "junior", "middle", "senior", "lead", "intern"];

type ApiResponse = { jobs: Job[]; page: number; hasMore: boolean; error?: string };

export function JobsFeedClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

  const loadingRef = useRef(false);

  const q = searchParams.get("q") || "";
  const tag = searchParams.get("tag") || "";
  const remote = searchParams.get("remote") || "";
  const seniority = searchParams.get("seniority") || "";

  const key = useMemo(() => JSON.stringify({ q, tag, remote, seniority }), [q, tag, remote, seniority]);

  const loadPage = useCallback(
    async (targetPage: number, replace: boolean) => {
      if (loadingRef.current) return;

      loadingRef.current = true;
      setLoading(true);

      try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (tag) params.set("tag", tag);
        if (remote) params.set("remote", remote);
        if (seniority) params.set("seniority", seniority);
        params.set("page", String(targetPage));

        const response = await fetch(`/api/jobs?${params.toString()}`, { cache: "no-store" });
        const data = (await response.json()) as ApiResponse;

        if (!response.ok || data.error) {
          return;
        }

        setJobs((prev) => (replace ? data.jobs : [...prev, ...data.jobs]));
        setPage(data.page);
        setHasMore(Boolean(data.hasMore));
      } finally {
        loadingRef.current = false;
        setLoading(false);
      }
    },
    [q, tag, remote, seniority]
  );

  useEffect(() => {
    setJobs([]);
    setPage(1);
    setHasMore(true);
    setOpenId(null);
    void loadPage(1, true);
  }, [key, loadPage]);

  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!sentinelRef.current || !hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (first?.isIntersecting && hasMore && !loadingRef.current) {
          void loadPage(page + 1, false);
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [page, hasMore, loadPage]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    const params = new URLSearchParams();
    const fq = String(formData.get("q") || "").trim();
    const ftag = String(formData.get("tag") || "").trim();
    const fremote = String(formData.get("remote") || "").trim();
    const fseniority = String(formData.get("seniority") || "").trim();

    if (fq) params.set("q", fq);
    if (ftag) params.set("tag", ftag);
    if (fremote) params.set("remote", fremote);
    if (fseniority) params.set("seniority", fseniority);

    const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
    router.push(url);
  }

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs Feed</h1>
        <p className="text-sm text-soft">Sorted by original publication time.</p>
      </div>

      <form onSubmit={onSubmit} className="grid gap-3 rounded-lg border border-line bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search by title, company, description"
          className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-ink lg:col-span-2"
        />

        <select name="tag" defaultValue={tag} className="rounded-md border border-line px-3 py-2 text-sm">
          {TAG_OPTIONS.map((item) => (
            <option key={item} value={item}>
              {item ? `tag: ${item}` : "all tags"}
            </option>
          ))}
        </select>

        <select name="remote" defaultValue={remote} className="rounded-md border border-line px-3 py-2 text-sm">
          <option value="">all locations</option>
          <option value="true">remote only</option>
        </select>

        <select name="seniority" defaultValue={seniority} className="rounded-md border border-line px-3 py-2 text-sm">
          {SENIORITY_OPTIONS.map((item) => (
            <option key={item} value={item}>
              {item ? `level: ${item}` : "all levels"}
            </option>
          ))}
        </select>

        <div className="sm:col-span-2 lg:col-span-5">
          <button className="rounded-md border border-ink bg-ink px-4 py-2 text-sm font-medium text-white" type="submit">
            Apply filters
          </button>
        </div>
      </form>

      <div className="space-y-3">
        {jobs.length === 0 && !loading ? <p className="text-sm text-soft">No jobs found.</p> : null}
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            isOpen={openId === job.id}
            onToggle={(id) => setOpenId((prev) => (prev === id ? null : id))}
          />
        ))}
      </div>

      <div ref={sentinelRef} className="h-10" />
      {loading ? <p className="text-sm text-soft">Loading more...</p> : null}
      {!hasMore && jobs.length > 0 ? <p className="text-sm text-soft">No more jobs.</p> : null}
    </section>
  );
}
