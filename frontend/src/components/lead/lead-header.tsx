"use client";

import { ArrowLeft, ArrowRight, Copy, Phone } from "lucide-react";
import { forwardRef } from "react";
import { toast } from "sonner";
import { TagBadge } from "@/components/tag-badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUpdateLead } from "@/hooks/use-lead-mutations";
import type { Lead } from "@/lib/types";

interface Props {
  lead: Lead;
  reps: string[];
  inCurrentFilter: boolean;
  onBack: () => void;
  onNext: (() => void) | null;
}

export const LeadHeader = forwardRef<HTMLHeadingElement, Props>(function LeadHeader(
  { lead, reps, inCurrentFilter, onBack, onNext },
  headingRef,
) {
  const update = useUpdateLead(lead.id);
  const copyPhone = async () => {
    try {
      await navigator.clipboard.writeText(lead.phone);
      toast.success("Phone number copied.");
    } catch {
      toast.error("Couldn't copy the number.");
    }
  };

  return (
    <header className="space-y-3">
      {/* Compact widths get a navigation row; wide screens fold "Next lead" into the name row. */}
      <div className="flex items-center justify-between gap-2 lg:hidden">
        <Button variant="ghost" onClick={onBack} className="-ml-2">
          <ArrowLeft aria-hidden />
          Back to queue
        </Button>
        {onNext && (
          <Button variant="outline" onClick={onNext}>
            Next lead
            <ArrowRight aria-hidden />
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="text-xl font-semibold text-balance outline-none"
        >
          {lead.name}
        </h2>
        <TagBadge label={lead.classification} />
        {!inCurrentFilter && (
          <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            Not in current filter
          </span>
        )}
        {onNext && (
          <Button variant="outline" onClick={onNext} className="ml-auto hidden lg:inline-flex">
            Next lead
            <ArrowRight aria-hidden />
          </Button>
        )}
      </div>
      <p className="text-sm text-muted-foreground">{lead.company}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <span className="inline-flex items-center gap-1">
          <Phone aria-hidden className="size-4 text-muted-foreground" />
          <a
            href={`tel:${lead.phone.replace(/[^\d+]/g, "")}`}
            className="tabular-nums underline-offset-2 hover:underline"
          >
            {lead.phone}
          </a>
          <Button variant="ghost" size="icon-sm" aria-label="Copy phone number" onClick={copyPhone}>
            <Copy aria-hidden />
          </Button>
        </span>
        <span className="text-muted-foreground">Source: {lead.source}</span>
        <label className="inline-flex items-center gap-2 text-muted-foreground">
          Assigned to
          <Select
            value={lead.assigned_rep}
            onValueChange={(rep) =>
              update.mutate(
                { assigned_rep: rep },
                {
                  onSuccess: () => toast.success(`Assigned to ${rep}.`),
                  onError: () => toast.error("Couldn't reassign the lead."),
                },
              )
            }
          >
            <SelectTrigger size="sm" aria-label="Assigned rep" className="min-w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {reps.map((rep) => (
                <SelectItem key={rep} value={rep}>
                  {rep}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
      </div>
    </header>
  );
});
