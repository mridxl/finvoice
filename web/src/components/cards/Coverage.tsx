/** How much of the month has actually been asked about.
 *
 * The thing a voice call cannot tell you is how much longer it is going to
 * take, and an open-ended conversation about money you may not have is a
 * stressful place to be left. Four categories, and each one is either untouched,
 * started, or closed by the user saying that is all of it.
 *
 * Read straight off the gaps the server already sends. A category that has been
 * settled sends no gap at all — absence is the signal, and absence cannot name
 * itself, which is the one reason the category list is mirrored here rather
 * than derived from the payload.
 */

import type { GapItem } from "@/cards";
import { cn } from "@/lib/utils";

/** `COVERAGE` in `server/domain/gaps.py`, in the order the agent asks. */
const CATEGORIES = [
  { id: "money_in", label: "Income" },
  { id: "essentials", label: "Essentials" },
  { id: "loans", label: "Loans" },
  { id: "cards", label: "Cards" },
] as const;

type State = "empty" | "partly" | "done";

export type Covered = {
  id: string;
  label: string;
  state: State;
  /** The one the agent is working through right now. */
  current: boolean;
};

export function coverage(gaps: GapItem[]): Covered[] {
  const open = new Map(gaps.filter((gap) => gap.coverage).map((gap) => [gap.fact_id, gap]));
  // The server ranks untouched categories first and unclosed ones last, each
  // in its own asking order, so the head of the coverage list is what the next
  // question is about — whether it is opening a category or sweeping one.
  const asking = gaps.find((gap) => gap.coverage)?.fact_id;
  return CATEGORIES.map((category) => {
    const gap = open.get(category.id);
    const state: State = !gap ? "done" : gap.field === "existence" ? "empty" : "partly";
    return { id: category.id, label: category.label, state, current: category.id === asking };
  });
}

const WORD: Record<State, string> = {
  done: "Done",
  partly: "Partly",
  empty: "Not yet",
};

export function Coverage({ items }: { items: Covered[] }) {
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
