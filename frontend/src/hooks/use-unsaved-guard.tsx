"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

interface Guard {
  setDirty: (dirty: boolean) => void;
  /** Resolves true when it is safe to leave the current lead. */
  confirmLeave: () => boolean;
}

const GuardContext = createContext<Guard>({ setDirty: () => {}, confirmLeave: () => true });

export function UnsavedGuardProvider({ children }: { children: ReactNode }) {
  const dirty = useRef(false);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (dirty.current) event.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  const setDirty = useCallback((value: boolean) => {
    dirty.current = value;
  }, []);
  const confirmLeave = useCallback(() => {
    if (!dirty.current) return true;
    const ok = window.confirm("Discard your unsaved draft?");
    if (ok) dirty.current = false;
    return ok;
  }, []);

  const value = useMemo(() => ({ setDirty, confirmLeave }), [setDirty, confirmLeave]);
  return <GuardContext.Provider value={value}>{children}</GuardContext.Provider>;
}

export function useUnsavedGuard(): Guard {
  return useContext(GuardContext);
}
