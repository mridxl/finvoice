/** The pieces every card is built from: a section, an amount, a date, a badge.
 *
 * Deliberately low-chrome. Ten bordered boxes stacked in a column read as ten
 * things of equal importance, which is the opposite of what a plan is.
 */

import type { ReactNode } from "react";

import type { Amount } from "@/cards";
import { cn } from "@/lib/utils";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** A titled block inside a panel, tinted for a moment when the server has just
 *  sent a new version of the card behind it. */
export function Section({
  title,
  lit,
  children,
  className,
}: {
  title?: string;
  lit?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-lg px-3 py-2 transition-colors duration-700",
        lit && "bg-accent/60",
        className,
      )}
    >
      {title && (
        <h3 className="text-muted-foreground mb-2 text-xs font-medium tracking-wider uppercase">
          {title}
        </h3>
      )}
      {children}
    </section>
  );
}

/** A figure that re-enters character by character whenever it changes.
 *
 * This is the correction made visible. "Correct an amount aloud and watch every
 * card move" is the exit condition for the whole card system, and a number that
 * silently swaps in flight is indistinguishable from one that never moved. The
 * `key` is the text, so React remounts on a change and the animation replays;
 * an unchanged figure never animates. */
export function PopNumber({ text, className }: { text: string; className?: string }) {
  const chars = [...text];
  return (
    <span key={text} className={cn("t-digit-group", className)}>
      {chars.map((char, i) => (
        <span
          key={i}
          className="t-digit"
          data-stagger={
            i === chars.length - 2 ? "1" : i === chars.length - 1 ? "2" : undefined
          }
        >
          {char === " " ? " " : char}
        </span>
      ))}
    </span>
  );
}

export function rupees(of: Amount): string {
  return of.text.startsWith("-") ? `-₹${of.text.slice(1)}` : `₹${of.text}`;
}

/** An amount as the server formatted it. The symbol is the only thing added
 *  here — `format_rupees` leaves it off because TTS cannot say it — and the
 *  minus has to step around it: the server's text is "-6,533.32", which becomes
 *  "₹-6,533.32" if the symbol is simply glued to the front. */
export function Rupees({ of, className }: { of: Amount; className?: string }) {
  return (
    <span className={cn("tabular-nums", of.paise < 0 && "text-destructive", className)}>
      {rupees(of)}
    </span>
  );
}

/** An ISO date as "20 Sep". Split rather than parsed: `new Date("2026-09-20")`
 *  is UTC midnight and slides to the day before in any western timezone, which
 *  on a calendar whose whole point is which day a bill lands on is not a
 *  rounding error. No arithmetic happens here — the date is the server's. */
export function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${Number(day)} ${MONTHS[Number(month) - 1]}`;
}

/** Which month a window row belongs to, for the one place it has to be obvious. */
export function monthOf(iso: string): string {
  return MONTHS[Number(iso.split("-")[1]) - 1];
}

export function Badge({
  tone = "muted",
  children,
}: {
  tone?: "muted" | "warn" | "bad";
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] font-medium",
        tone === "muted" && "bg-muted text-muted-foreground",
        tone === "warn" && "bg-amber-500/15 text-amber-700 dark:text-amber-400",
        tone === "bad" && "bg-destructive/15 text-destructive",
      )}
    >
      {children}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground text-sm">{children}</p>;
}
