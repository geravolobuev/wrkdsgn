import { Suspense } from "react";

import { JobsFeedClient } from "@/components/jobs-feed-client";

export default function JobsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-soft">Loading jobs...</p>}>
      <JobsFeedClient />
    </Suspense>
  );
}
