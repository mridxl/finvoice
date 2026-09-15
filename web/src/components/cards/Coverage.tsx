/** How much of the month has actually been asked about.
 *
 * The thing a voice call cannot tell you is how much longer it is going to
 * take, and an open-ended conversation about money you may not have is a
 * stressful place to be left. Four categories, and each one is either untouched,
 * started, or closed by the user saying that is all of it.
 *
 * The states are the server's, read off `missing_info.coverage`. They used to be
 * derived here from the gaps, which meant mirroring the category list: a settled
 * category sends no gap at all, and absence cannot name itself. Two copies of
 * `COVERAGE` was one too many — this file now renders four rows and decides
 * nothing.
 */

import type { CoverageItem } from "@/cards";
import { cn } from "@/lib/utils";

const WORD: Record<CoverageItem["state"], string> = {
  done: "Done",
  partly: "Partly",
  empty: "Not yet",
};

export function Coverage({ items }: { items: CoverageItem[] }) {
  return (
    <ol className="grid grid-cols-4 gap-2.5">
      {items.map((item) => (
        <li key={item.id}>
          <div
            className={cn(
              "h-1 rounded-full transition-colors duration-700",
              item.state === "done" && "bg-positive",
              item.state === "partly" && "bg-foreground/30",
              item.state === "empty" && "bg-border",
              // Outranks the state colour: where the conversation is right now
              // matters more than how far it has got.
              item.current && "bg-foreground",
            )}
          />
          <p className="mt-1.5 truncate text-xs font-medium">{item.label}</p>
          <p className="text-muted-foreground truncate text-[11px]">
            {item.current ? "Asking now" : WORD[item.state]}
          </p>
        </li>
      ))}
    </ol>
  );
}
