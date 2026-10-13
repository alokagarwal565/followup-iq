import { Suspense } from "react";
import { Dashboard } from "@/components/dashboard";
import { Skeleton } from "@/components/ui/skeleton";

// The dashboard reads the selected lead from the URL, so it renders on the client under a
// Suspense boundary while the static shell is prerendered.
export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-screen-2xl space-y-4 px-4 py-6">
          <Skeleton className="h-10 w-full max-w-xl" />
          <Skeleton className="h-64 w-full" />
        </div>
      }
    >
      <Dashboard />
    </Suspense>
  );
}
