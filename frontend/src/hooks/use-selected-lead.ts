"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** The open lead lives in the URL (?lead=…) so refresh, back and shared links all work. */
export function useSelectedLead(): [
  string | null,
  (id: string | null, opts?: { replace?: boolean }) => void,
] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selected = params.get("lead");

  const select = useCallback(
    (id: string | null, opts?: { replace?: boolean }) => {
      const next = new URLSearchParams(params.toString());
      if (id) next.set("lead", id);
      else next.delete("lead");
      const query = next.toString();
      const href = query ? `${pathname}?${query}` : pathname;
      if (opts?.replace) router.replace(href, { scroll: false });
      else router.push(href, { scroll: false });
    },
    [params, pathname, router],
  );

  return [selected, select];
}
