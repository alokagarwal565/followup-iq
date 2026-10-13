"use client";

import { useCallback, useState } from "react";

const STORAGE_KEY = "followupiq.rep";

function readStored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // Storage can be blocked (private mode, policies) or absent on the server; nothing is remembered.
    return null;
  }
}

/** The rep a person is viewing as, remembered per browser. `null` means all reps. */
export function useRepFilter(validReps: string[]): [string | null, (rep: string | null) => void] {
  const [chosen, setChosen] = useState<string | null>(readStored);
  // A rep removed from the team since it was stored falls back to "All reps".
  const rep = chosen && validReps.includes(chosen) ? chosen : null;

  const update = useCallback((next: string | null) => {
    setChosen(next);
    try {
      if (next) window.localStorage.setItem(STORAGE_KEY, next);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // See readStored(): failing to persist is harmless.
    }
  }, []);

  return [rep, update];
}
