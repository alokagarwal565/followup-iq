"use client";

import { Keyboard, Plus, Search } from "lucide-react";
import { forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateOnly, formatFullDate } from "@/lib/format";
import type { Meta } from "@/lib/types";

const ALL_REPS = "__all";

const SHORTCUTS: [string, string][] = [
  ["j / ↓", "Next lead"],
  ["k / ↑", "Previous lead"],
  ["/", "Search"],
  ["n", "Add lead"],
  ["Esc", "Back to queue (mobile)"],
  ["Ctrl/⌘ + S", "Save draft"],
];

interface Props {
  meta: Meta;
  rep: string | null;
  onRepChange: (rep: string | null) => void;
  search: string;
  onSearchChange: (value: string) => void;
  onAddLead: () => void;
}

export const AppHeader = forwardRef<HTMLInputElement, Props>(function AppHeader(
  { meta, rep, onRepChange, search, onSearchChange, onAddLead },
  searchRef,
) {
  return (
    <header className="shrink-0 border-b bg-card">
      {/* Two rows on phones (brand, date, Add lead / rep, search), one row on wide screens. */}
      <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:gap-x-4">
        <div className="order-1 mr-auto min-w-0">
          <p className="text-lg font-semibold tracking-tight">FollowUpIQ</p>
          <p className="hidden text-sm text-muted-foreground sm:block">
            Know who to follow up with. Know what to say.
          </p>
        </div>
        <p
          className="order-2 text-sm text-muted-foreground tabular-nums"
          title={`${formatFullDate(meta.today)} (${meta.business_tz})`}
        >
          {formatDateOnly(meta.today)}
        </p>
        <Select
          value={rep ?? ALL_REPS}
          onValueChange={(value) => onRepChange(value === ALL_REPS ? null : value)}
        >
          <SelectTrigger aria-label="Viewing leads for" className="order-4 min-w-44 lg:order-3">
            <span className="text-muted-foreground">Viewing:</span>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_REPS}>All reps</SelectItem>
            {meta.reps.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative order-5 min-w-40 flex-1 sm:w-64 sm:flex-none lg:order-4">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search leads"
            aria-label="Search leads"
            className="h-10 pl-8"
          />
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="icon-lg"
              aria-label="Keyboard shortcuts"
              className="hidden lg:order-5 lg:inline-flex"
            >
              <Keyboard aria-hidden />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-64">
            <p className="mb-2 text-sm font-semibold">Keyboard shortcuts</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
              {SHORTCUTS.map(([keys, action]) => (
                <div key={keys} className="contents">
                  <dt>
                    <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs">{keys}</kbd>
                  </dt>
                  <dd className="text-muted-foreground">{action}</dd>
                </div>
              ))}
            </dl>
          </PopoverContent>
        </Popover>
        <Button size="lg" onClick={onAddLead} className="order-3 lg:order-last">
          <Plus aria-hidden />
          Add lead
        </Button>
      </div>
    </header>
  );
});
