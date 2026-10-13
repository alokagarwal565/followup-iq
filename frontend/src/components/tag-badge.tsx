import { CircleDashed, Flame, Snowflake, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Classification } from "@/lib/types";

const STYLES: Record<Classification, { icon: typeof Flame; className: string }> = {
  Hot: { icon: Flame, className: "bg-hot-tint text-hot-foreground" },
  Warm: { icon: Sun, className: "bg-warm-tint text-warm-foreground" },
  Cold: { icon: Snowflake, className: "bg-cold-tint text-cold-foreground" },
};

/** The tag is always icon + word + tint: colour alone never carries the meaning. */
export function TagBadge({
  label,
  className,
}: {
  label: Classification | null;
  className?: string;
}) {
  if (!label) {
    return (
      <span
        className={cn(
          "inline-flex h-6 items-center gap-1 rounded-md bg-muted px-2 text-xs font-medium text-muted-foreground",
          className,
        )}
      >
        <CircleDashed aria-hidden className="size-3.5" />
        Not tagged yet
      </span>
    );
  }
  const { icon: Icon, className: tone } = STYLES[label];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1 rounded-md px-2 text-xs font-semibold",
        tone,
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  );
}
