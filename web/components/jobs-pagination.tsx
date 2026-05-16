import Link from "next/link";

import type { JobsFilters } from "@/types/job";

function withPage(filters: JobsFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.remote) params.set("remote", filters.remote);
  if (filters.seniority) params.set("seniority", filters.seniority);
  params.set("page", String(page));
  return `/jobs?${params.toString()}`;
}

export function JobsPagination({ page, hasMore, filters }: { page: number; hasMore: boolean; filters: JobsFilters }) {
  return (
    <div className="flex items-center justify-between border-t border-line pt-4">
      <div>
        {page > 1 ? (
          <Link className="link text-sm" href={withPage(filters, page - 1)}>
            Previous
          </Link>
        ) : null}
      </div>
      <p className="text-sm text-soft">Page {page}</p>
      <div>
        {hasMore ? (
          <Link className="link text-sm" href={withPage(filters, page + 1)}>
            Next
          </Link>
        ) : null}
      </div>
    </div>
  );
}
