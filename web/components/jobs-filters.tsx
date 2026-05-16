import type { JobsFilters } from "@/types/job";

const SENIORITY_OPTIONS = ["", "junior", "middle", "senior", "lead", "intern"];
const TAG_OPTIONS = ["", "ux", "ui", "product", "graphic", "motion", "brand", "web", "mobile", "figma", "freelance"];

export function JobsFiltersForm({ filters }: { filters: JobsFilters }) {
  return (
    <form action="/jobs" className="grid gap-3 rounded-lg border border-line bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
      <input
        type="text"
        name="q"
        defaultValue={filters.q || ""}
        placeholder="Search by title, company, description"
        className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-ink lg:col-span-2"
      />

      <select name="tag" defaultValue={filters.tag || ""} className="rounded-md border border-line px-3 py-2 text-sm">
        {TAG_OPTIONS.map((tag) => (
          <option key={tag} value={tag}>
            {tag ? `tag: ${tag}` : "all tags"}
          </option>
        ))}
      </select>

      <select
        name="remote"
        defaultValue={filters.remote || ""}
        className="rounded-md border border-line px-3 py-2 text-sm"
      >
        <option value="">all locations</option>
        <option value="true">remote only</option>
      </select>

      <select
        name="seniority"
        defaultValue={filters.seniority || ""}
        className="rounded-md border border-line px-3 py-2 text-sm"
      >
        {SENIORITY_OPTIONS.map((level) => (
          <option key={level} value={level}>
            {level ? `level: ${level}` : "all levels"}
          </option>
        ))}
      </select>

      <div className="sm:col-span-2 lg:col-span-5">
        <button className="rounded-md border border-ink bg-ink px-4 py-2 text-sm font-medium text-white" type="submit">
          Apply filters
        </button>
      </div>
    </form>
  );
}
