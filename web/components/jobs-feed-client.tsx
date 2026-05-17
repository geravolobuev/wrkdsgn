"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { JobCard } from "@/components/job-card";
import type { Job } from "@/types/job";

const SPECIALIZATIONS = [
  "",
  "branding",
  "graphic_design",
  "product_design",
  "ux",
  "ui",
  "uxui",
  "motion",
  "3d",
  "illustration",
  "art_direction",
  "creative_direction",
  "visual_design",
  "web_design",
  "industrial_design",
  "service_design",
  "research",
  "design_ops",
];
const LEVELS = ["", "intern", "junior", "middle", "senior", "lead", "head", "director"];
const REMOTE_TYPES = ["", "remote", "hybrid", "onsite"];
const EMPLOYMENT_TYPES = ["", "full_time", "part_time", "contract", "freelance", "internship"];

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
  const level = searchParams.get("level") || "";
  const city = searchParams.get("city") || "";
  const country = searchParams.get("country") || "";
  const remoteType = searchParams.get("remote_type") || "";
  const employmentType = searchParams.get("employment_type") || "";

  const key = useMemo(
    () => JSON.stringify({ q, specialization, level, city, country, remoteType, employmentType }),
    [q, specialization, level, city, country, remoteType, employmentType]
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
        if (level) params.set("level", level);
        if (city) params.set("city", city);
        if (country) params.set("country", country);
        if (remoteType) params.set("remote_type", remoteType);
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
    [q, specialization, level, city, country, remoteType, employmentType]
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
    const flevel = String(formData.get("level") || "").trim();
    const fcity = String(formData.get("city") || "").trim();
    const fcountry = String(formData.get("country") || "").trim();
    const fremoteType = String(formData.get("remote_type") || "").trim();
    const femploymentType = String(formData.get("employment_type") || "").trim();

    if (fq) params.set("q", fq);
    if (fspecialization) params.set("specialization", fspecialization);
    if (flevel) params.set("level", flevel);
    if (fcity) params.set("city", fcity);
    if (fcountry) params.set("country", fcountry);
    if (fremoteType) params.set("remote_type", fremoteType);
    if (femploymentType) params.set("employment_type", femploymentType);

    const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
    router.push(url);
  }

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs Feed</h1>
        <p className="text-sm text-soft">AI-enriched structured filters. Sorted by original publication time.</p>
      </div>

      <form onSubmit={onSubmit} className="grid gap-3 rounded-lg border border-line bg-white p-4 sm:grid-cols-2 lg:grid-cols-7">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search title/company/description"
          className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-ink lg:col-span-2"
        />

        <select name="specialization" defaultValue={specialization} className="rounded-md border border-line px-3 py-2 text-sm">
          {SPECIALIZATIONS.map((item) => (
            <option key={item} value={item}>{item || "all specializations"}</option>
          ))}
        </select>

        <select name="level" defaultValue={level} className="rounded-md border border-line px-3 py-2 text-sm">
          {LEVELS.map((item) => (
            <option key={item} value={item}>{item || "all levels"}</option>
          ))}
        </select>

        <input
          type="text"
          name="city"
          defaultValue={city}
          placeholder="City"
          className="rounded-md border border-line px-3 py-2 text-sm"
        />

        <input
          type="text"
          name="country"
          defaultValue={country}
          placeholder="Country"
          className="rounded-md border border-line px-3 py-2 text-sm"
        />

        <select name="remote_type" defaultValue={remoteType} className="rounded-md border border-line px-3 py-2 text-sm">
          {REMOTE_TYPES.map((item) => (
            <option key={item} value={item}>{item || "all remote types"}</option>
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
