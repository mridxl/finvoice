/** Every card body except the ledger, which is big enough to live on its own. */

import type { ActionItem, Bodies, FactItem, GapItem } from "@/cards";
import { Badge, Empty, Rupees, rupees, shortDate } from "./parts";

/** The working behind the verdict, not the verdict. The status, the shortfall
 *  and the day it bites are said once, up in the headline and the stat tiles —
 *  repeating them here is how a panel turns back into a wall. */
export function BottomLine({ body }: { body: Bodies["bottom_line"] }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Paying every commitment in full and on time, the month would be short{" "}
        <Rupees of={body.gap_if_all_paid} className="text-foreground font-medium" />.
      </p>
      {body.assumptions.length > 0 && (
        <div>
          <h4 className="text-muted-foreground mb-1 text-xs font-medium">
            What the plan assumed
          </h4>
          <ul className="text-muted-foreground space-y-1 text-xs">
            {body.assumptions.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function FactList({ items }: { items: FactItem[] }) {
  if (items.length === 0) return <Empty>Nothing recorded yet.</Empty>;
  return (
    <ul className="divide-border divide-y text-sm">
      {items.map((fact) => (
        <li key={fact.fact_id} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0">
            <span className="font-medium">{fact.label}</span>
            <span className="text-muted-foreground ml-2 text-xs">{whenSaid(fact)}</span>
            {fact.certainty !== "stated" && (
              <span className="ml-2">
                <Badge tone={fact.certainty === "unknown" ? "bad" : "warn"}>{fact.certainty}</Badge>
              </span>
            )}
            {fact.contested && (
              <span className="ml-2">
                <Badge tone="bad">two figures given</Badge>
              </span>
            )}
          </span>
          <span className="shrink-0 text-right">
            {/* The proof that a correction rippled: what it was, beside what it is. */}
            {fact.corrected_from && (
              <span className="text-muted-foreground mr-2 text-xs line-through">
                {rupees(fact.corrected_from)}
              </span>
            )}
            {fact.amount ? <Rupees of={fact.amount} className="font-semibold" /> : "—"}
            {/* What they said, under what the plan uses. Without it the card
                asserts a figure they never gave and the badge is the only clue. */}
            {fact.amount_range && (
              <span className="text-muted-foreground block text-xs">
                {rupees(fact.amount_range.low)}–{rupees(fact.amount_range.high)}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** What the user said about timing, not where the planner put it. A day of the
 *  month is not a date until the window decides which month it falls in — that
 *  is the ledger's job, and saying "the 20th" here would invite the same
 *  ordering mistake the spoken plan used to make. */
function whenSaid(fact: FactItem): string {
  if (fact.spread) return "across the month";
  if (fact.day === null) return "no date given";
  return `day ${fact.day} of the month`;
}

export function Actions({ body }: { body: Bodies["actions"] }) {
  const groups: [string, ActionItem[]][] = [
    ["Cut", body.cuts],
    ["Met by arrangement", body.arranged],
    ["Cannot be paid", body.unpaid],
  ];
  if (groups.every(([, items]) => items.length === 0)) {
    return <Empty>Nothing has had to give way.</Empty>;
  }
  return (
    <div className="space-y-3 text-sm">
      {groups.map(([heading, items]) =>
        items.length === 0 ? null : (
          <div key={heading}>
            <h3 className="text-muted-foreground mb-1 text-xs font-medium">{heading}</h3>
            <ul className="space-y-2">
              {items.map((action) => (
                <li key={action.fact_id}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{action.label}</span>
                    <span className="shrink-0">
                      <Rupees of={action.amount} className="font-semibold" />
                      {action.on && (
                        <span className="text-muted-foreground ml-2 text-xs">
                          {shortDate(action.on)}
                        </span>
                      )}
                    </span>
                  </div>
                  {action.paid.paise > 0 && (
                    <p className="text-muted-foreground text-xs">
                      Paying <Rupees of={action.paid} />, still owed{" "}
                      <Rupees of={action.outstanding} />.
                    </p>
                  )}
                  <p className="text-muted-foreground text-xs">{action.reason}</p>
                </li>
              ))}
            </ul>
          </div>
        ),
      )}
    </div>
  );
}

export function MissingInfo({ body }: { body: Bodies["missing_info"] }) {
  if (body.items.length === 0) return <Empty>Nothing left worth asking.</Empty>;
  // A coverage gap and a measured one are different questions — "we have not
  // asked" against "we asked, and the answer is imprecise". Rendering them
  // alike is how a list of ten stops being read at all.
  const measured = body.items.filter((gap) => !gap.coverage);
  const coverage = body.items.filter((gap) => gap.coverage);
  return (
    <div className="space-y-3 text-sm">
      {measured.length > 0 && <GapList items={measured} />}
      {coverage.length > 0 && (
        <div>
          <h3 className="text-muted-foreground mb-1 text-xs font-medium">Not settled yet</h3>
          <GapList items={coverage} />
        </div>
      )}
    </div>
  );
}

function GapList({ items }: { items: GapItem[] }) {
  return (
    <ul className="space-y-2">
      {items.map((gap) => (
        <li key={`${gap.fact_id}:${gap.field}`}>
          <div className="flex items-baseline gap-2">
            <Badge tone={gap.impact === "high" ? "bad" : gap.impact === "medium" ? "warn" : "muted"}>
              {gap.impact}
            </Badge>
            <span className="font-medium">{gap.label}</span>
          </div>
          <p className="text-muted-foreground text-xs">{gap.why}</p>
        </li>
      ))}
    </ul>
  );
}
