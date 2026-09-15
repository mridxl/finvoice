/** The thirty days, one row each: the card that lets a reader check the arithmetic.
 *
 * SPEC 3.4 asks for calculations that are visible and testable, and this is the
 * visible half — every entry the planner placed, on the day it placed it, with
 * the balance it left behind. Nothing is summed here; `closing` is the server's.
 *
 * Empty days are rows too. A table that skips them hides the thing that breaks a
 * month, which is how long the balance sits low between one date and the next.
 */

import type { Bodies, LedgerRow } from "@/cards";
import { cn } from "@/lib/utils";

import { Rupees, monthOf, shortDate } from "./parts";

export function Ledger({ body }: { body: Bodies["ledger"] }) {
  // No scroll container of its own: the panel around it already scrolls, and
  // nesting two makes the thirty rows feel like a widget rather than the record.
  return (
    <div>
      <table className="w-full text-sm">
        <thead className="bg-card text-muted-foreground sticky top-0 text-left text-xs">
          <tr>
            <th className="py-1 pr-2 font-medium">Day</th>
            <th className="py-1 pr-2 font-medium">What lands</th>
            <th className="py-1 pr-2 text-right font-medium">In or out</th>
            <th className="py-1 text-right font-medium">Balance</th>
          </tr>
        </thead>
        <tbody>
          {body.rows.map((row, index) => (
            <Row key={row.on} row={row} opensAMonth={index > 0 && startsNewMonth(body.rows, index)} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Where the window crosses into the next month. The heavier rule is the point
 *  of the card: read as bare days, the twentieth appears to come before the
 *  fifth, and a plan explained in that order cannot produce its own shortfall. */
function startsNewMonth(rows: LedgerRow[], index: number): boolean {
  return monthOf(rows[index].on) !== monthOf(rows[index - 1].on);
}

function Row({ row, opensAMonth }: { row: LedgerRow; opensAMonth: boolean }) {
  const quiet = row.entries.length === 0;
  return (
    <tr
      className={cn(
        "border-border/60 border-t align-top",
        opensAMonth && "border-foreground/40 border-t-2",
        row.closing.paise < 0 && "bg-destructive/5",
      )}
    >
      <td className={cn("py-1 pr-2 whitespace-nowrap", quiet && "text-muted-foreground")}>
        {shortDate(row.on)}
      </td>
      <td className="py-1 pr-2">
        {row.entries.map((entry) => (
          <div key={`${entry.label}:${entry.amount.paise}`}>{entry.label}</div>
        ))}
      </td>
      <td className="py-1 pr-2 text-right">
        {row.entries.map((entry) => (
          <div key={`${entry.label}:${entry.amount.paise}`}>
            <Rupees of={entry.amount} />
          </div>
        ))}
      </td>
      <td
        className={cn(
          "py-1 text-right font-medium",
          quiet && "text-muted-foreground font-normal",
        )}
      >
        <Rupees of={row.closing} />
      </td>
    </tr>
  );
}
