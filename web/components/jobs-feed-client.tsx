"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { JobCard } from "@/components/job-card";
import type { Job } from "@/types/job";

const ROLES = [
  "",
  "Graphic Designer",
  "Brand Designer",
  "Visual Designer",
  "Communication Designer",
  "Digital Designer",
  "Marketing Designer",
  "Presentation Designer",
  "Editorial Designer",
  "Packaging Designer",
  "Information Designer",
  "Key Visual Designer",
  "Motion Designer",
  "3D Designer",
  "Web Designer",
  "UI Designer",
  "Art Director",
  "Creative Director",
  "Design Director",
  "Illustrator",
  "Type Designer",
  "Design Manager",
];
const SENIORITIES = ["", "Junior", "Middle", "Senior", "Lead", "Head / Director", "Unknown"];
const WORK_FORMATS = ["", "Remote", "Hybrid", "On-site", "Unknown"];
const EMPLOYMENT_TYPES = ["", "Full-time", "Part-time", "Contract", "Freelance", "Internship", "Unknown"];

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
  const specialization = searchParams.get("specialization") || "";
  const seniority = searchParams.get("seniority") || "";
  const workFormat = searchParams.get("work_format") || "";
  const employmentType = searchParams.get("employment_type") || "";

  const key = useMemo(
    () => JSON.stringify({ q, specialization, seniority, workFormat, employmentType }),
    [q, specialization, seniority, workFormat, employmentType]
  );

  const loadPage = useCallback(
    async (targetPage: number, replace: boolean) => {
      if (loadingRef.current) return;

      loadingRef.current = true;
      setLoading(true);

      try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (specialization) params.set("specialization", specialization);
        if (seniority) params.set("seniority", seniority);
        if (workFormat) params.set("work_format", workFormat);
        if (employmentType) params.set("employment_type", employmentType);
        params.set("page", String(targetPage));

        const response = await fetch(`/api/jobs?${params.toString()}`, { cache: "no-store" });
        const data = (await response.json()) as ApiResponse;

        if (!response.ok || data.error) return;

        setJobs((prev) => (replace ? data.jobs : [...prev, ...data.jobs]));
        setPage(data.page);
        setHasMore(Boolean(data.hasMore));
      } finally {
        loadingRef.current = false;
        setLoading(false);
      }
    },
    [q, specialization, seniority, workFormat, employmentType]
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
    const fspecialization = String(formData.get("specialization") || "").trim();
    const fseniority = String(formData.get("seniority") || "").trim();
    const fworkFormat = String(formData.get("work_format") || "").trim();
    const femploymentType = String(formData.get("employment_type") || "").trim();

    if (fq) params.set("q", fq);
    if (fspecialization) params.set("specialization", fspecialization);
    if (fseniority) params.set("seniority", fseniority);
    if (fworkFormat) params.set("work_format", fworkFormat);
    if (femploymentType) params.set("employment_type", femploymentType);

    const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
    router.push(url);
  }

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs Feed</h1>
        <p className="text-sm text-soft">AI-curated roles for graphic & creative design.</p>
      </div>

      <form onSubmit={onSubmit} className="grid gap-3 rounded-lg border border-line bg-white p-4 sm:grid-cols-2 lg:grid-cols-7">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search title/description"
          className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-ink lg:col-span-2"
        />

        <select name="specialization" defaultValue={specialization} className="rounded-md border border-line px-3 py-2 text-sm">
          {ROLES.map((item) => (
            <option key={item} value={item}>{item || "all roles"}</option>
          ))}
        </select>

        <select name="seniority" defaultValue={seniority} className="rounded-md border border-line px-3 py-2 text-sm">
          {SENIORITIES.map((item) => (
            <option key={item} value={item}>{item || "all levels"}</option>
          ))}
        </select>


        <select name="work_format" defaultValue={workFormat} className="rounded-md border border-line px-3 py-2 text-sm">
          {WORK_FORMATS.map((item) => (
            <option key={item} value={item}>{item || "all work formats"}</option>
          ))}
        </select>

        <select name="employment_type" defaultValue={employmentType} className="rounded-md border border-line px-3 py-2 text-sm">
          {EMPLOYMENT_TYPES.map((item) => (
            <option key={item} value={item}>{item || "all employment types"}</option>
          ))}
        </select>

        <div className="sm:col-span-2 lg:col-span-7">
          <button className="rounded-md border border-ink bg-ink px-4 py-2 text-sm font-medium text-white" type="submit">
            Apply filters
          </button>
        </div>
      </form>

      <div className="space-y-3">
        {jobs.length === 0 && !loading ? <p className="text-sm text-soft">No jobs found.</p> : null}
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} isOpen={openId === job.id} onToggle={(id) => setOpenId((prev) => (prev === id ? null : id))} />
        ))}
      </div>

      <div ref={sentinelRef} className="h-10" />
      {loading ? <p className="text-sm text-soft">Loading more...</p> : null}
      {!hasMore && jobs.length > 0 ? <p className="text-sm text-soft">No more jobs.</p> : null}
    </section>
  );
}
