/** The card payloads, exactly as `server/domain/cards.py` sends them.
 *
 * Mirrored rather than inferred, and deliberately never widened: every amount
 * arrives as paise plus the text and the spoken form, so there is nothing here
 * for the browser to work out. A field invented on this side would be a number
 * the planner never computed, which is the one thing the whole design forbids.
 */

export type Amount = { paise: number; text: string; speech: string };

export type Certainty = "stated" | "estimated" | "unknown";
export type Status = "feasible" | "tight" | "infeasible";

export type FactItem = {
  fact_id: string;
  label: string;
  kind: string;
  amount: Amount | null;
  /** The ends the user gave, when they gave a range. `amount` is the middle of
   *  them — the figure the planner works from, which nobody said out loud. */
  amount_range: { low: Amount; high: Amount } | null;
  day: number | null;
  spread: boolean;
  certainty: Certainty;
  contested: boolean;
  /** Set only after a correction: what the amount used to be. */
  corrected_from: Amount | null;
};

export type ActionItem = {
  fact_id: string;
  label: string;
  kind: string;
  amount: Amount;
  paid: Amount;
  outstanding: Amount;
  on: string | null;
  reason: string;
};

export type GapItem = {
  fact_id: string;
  label: string;
  field: "amount" | "day" | "existence" | "completeness";
  impact: "high" | "medium" | "low";
  why: string;
  low: number | null;
  high: number | null;
  swing: number;
  coverage: boolean;
  ask: string;
};

/** One of the four categories the intake has to get through, as the server
 *  ranks them. `partly` means something is recorded and nobody has said it is
 *  all of it, which is not the same as finished. */
export type CoverageItem = {
  id: string;
  label: string;
  state: "empty" | "partly" | "done";
  /** The one the agent is working through right now. */
  current: boolean;
};

export type Entry = { label: string; kind: string; amount: Amount };
export type LedgerRow = { on: string; entries: Entry[]; closing: Amount };
export type CalendarDay = { on: string; net: Amount; closing: Amount; negative: boolean };

export type Bodies = {
  cash_position: { opening: Amount; closing: Amount; lowest: Amount };
  income: { items: FactItem[] };
  obligations: { items: FactItem[] };
  essentials: { items: FactItem[] };
  optionals: { items: FactItem[] };
  calendar: { days: CalendarDay[] };
  bottom_line: {
    status: Status;
    gap_if_all_paid: Amount;
    still_short: Amount;
    first_shortfall_on: string | null;
    assumptions: string[];
  };
  missing_info: {
    items: GapItem[];
    /** No question left that would change the plan. The same test the agent
     *  gets back from `open_questions`, so the screen and the voice switch
     *  phase together instead of a turn apart. */
    enough_information: boolean;
    coverage: CoverageItem[];
  };
  actions: { cuts: ActionItem[]; arranged: ActionItem[]; unpaid: ActionItem[] };
  ledger: { rows: LedgerRow[] };
};

export type CardId = keyof Bodies;

export type Card<K extends CardId = CardId> = {
  id: K;
  title: string;
  revision: number;
  digest: string;
  body: Bodies[K];
};

export type Deck = { [K in CardId]?: Card<K> };
