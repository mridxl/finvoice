/** The one thing the call is about, in the two shapes the call actually has.
 *
 * While the agent is still asking what the month contains, a plan is not a
 * plan: every figure is computed over whichever categories happen to have come
 * up, and laying them out like a finished statement asserts something nobody
 * has established. This screen used to do exactly that — three figures and a
 * curve over a quarter of the facts, with the tab switching under a user who
 * was mid-sentence.
 *
 * So there are two screens. The first says what has been covered and what has
 * been heard back. The second says what the month does and what has to give
 * way. The switch is the server's own coverage signal, not a timer and not a
 * guess: every category has either been settled or has something in it.
 */

import { useLayoutEffect, useRef, useState } from "react";

import type { Amount, CardId, Deck, Status } from "@/cards";
import { cn } from "@/lib/utils";

import { BalanceCurve } from "./BalanceCurve";
import { Actions, BottomLine, FactList, MissingInfo } from "./Cards";
import { Coverage, coverage, type Covered } from "./Coverage";
import { Ledger } from "./Ledger";
import { Empty, PopNumber, Section, rupees, shortDate } from "./parts";

export function Workspace({ deck, lit }: { deck: Deck; lit: Set<CardId> }) {
  if (!deck.bottom_line) return <Waiting />;
  const covered = coverage(deck.missing_info?.body.items ?? []);
  const gathering = covered.some((category) => category.state === "empty");

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      {gathering ? (
        <Gathering deck={deck} lit={lit} covered={covered} />
      ) : (
        <Ready deck={deck} lit={lit} />
      )}
    </div>
  );
}

function Waiting() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <h2 className="font-display text-3xl tracking-tight">Thirty days, worked out together.</h2>
      <p className="text-muted-foreground max-w-md text-sm text-pretty">
        Start the call and talk through what comes in and what has to go out. Everything you say
        shows up here as you go, so you can check it while you talk.
      </p>
    </div>
  );
}

/** Nothing here is a plan. What is on screen is the state of the conversation
 *  and a read-back of every figure given so far, which is the only thing the
 *  user can usefully check while they are still talking. */
function Gathering({ deck, lit, covered }: { deck: Deck; lit: Set<CardId>; covered: Covered[] }) {
  return (
    <>
      <header>
        <h2 className="font-display text-[1.75rem] leading-[1.15] tracking-tight text-balance">
          Still working out the month.
        </h2>
        <p className="text-muted-foreground mt-2 text-sm text-pretty">
          A few things still to cover. Leave one out and the amount left over at the end will look
          bigger than it really is.
        </p>
      </header>

      <Coverage items={covered} />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <Told deck={deck} lit={lit} />
      </div>
    </>
  );
}

/** The plan, in the order the questions arrive: how did it go, what do I have
 *  to do about it, where does it break, and what were the numbers. What has to
 *  give way used to sit inside a tab, two clicks from the verdict that made it
 *  necessary — it is the only part of this screen that is advice. */
function Ready({ deck, lit }: { deck: Deck; lit: Set<CardId> }) {
  const [tab, setTab] = useState<TabId>("told");
  const plan = deck.bottom_line!.body;

  return (
    <>
      <header>
        <h2 className="font-display text-[1.75rem] leading-[1.15] tracking-tight text-balance">
          {READY[plan.status]}
        </h2>
        <p className="text-muted-foreground mt-2 text-sm text-pretty">
          {plan.first_shortfall_on
            ? `Paying everything on time, you run short on ${shortDate(plan.first_shortfall_on)}.`
            : "You don't run short at any point in the thirty days."}
        </p>
      </header>

      {deck.actions && (
        <Section title="What has to give way" lit={lit.has("actions")} className="bg-muted/40 px-4 py-3">
          <Actions body={deck.actions.body} />
        </Section>
      )}

      {deck.ledger && deck.calendar && (
        <BalanceCurve ledger={deck.ledger.body} calendar={deck.calendar.body} />
      )}

      <Figures deck={deck} />

      <Tabs open={tab} lit={lit} onPick={setTab} />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "told" ? <Told deck={deck} lit={lit} /> : <Working deck={deck} lit={lit} />}
      </div>
    </>
  );
}

const READY: Record<Status, string> = {
  feasible: "The month works.",
  tight: "It works, but only just.",
  infeasible: "The money doesn't stretch to cover everything.",
};

const GROUPS = [
  { id: "income", title: "Income" },
  { id: "essentials", title: "Essentials" },
  { id: "obligations", title: "Loans and cards" },
  { id: "optionals", title: "Optional spending" },
] as const;

/** Every figure the user has given, in one list rather than behind three tabs.
 *  This is the read-back made visible, and the read-back is a correctness
 *  mechanism: a category the user cannot see is one they cannot correct. Empty
 *  groups are absent — a heading over "nothing recorded yet" is a container
 *  pretending to be content. */
function Told({ deck, lit }: { deck: Deck; lit: Set<CardId> }) {
  const groups = GROUPS.filter((group) => (deck[group.id]?.body.items.length ?? 0) > 0);
  if (groups.length === 0) {
    return <Empty>Nothing yet. Every figure you give shows up here, so you can check it as you go.</Empty>;
  }
  return (
    <div className="space-y-2">
      {groups.map((group) => (
        <Section key={group.id} title={group.title} lit={lit.has(group.id)}>
          <FactList items={deck[group.id]!.body.items} />
        </Section>
      ))}
    </div>
  );
}

/** Where the number came from: what was assumed, what is still unsure, and the
 *  day-by-day it was built out of. Auditable on purpose — the claim this project
 *  makes is that no figure was the model's invention, and that claim is worth
 *  nothing if the derivation is not on screen. */
function Working({ deck, lit }: { deck: Deck; lit: Set<CardId> }) {
  return (
    <div className="space-y-2">
      {deck.bottom_line && (
        <Section title="Where the gap comes from" lit={lit.has("bottom_line")}>
          <BottomLine body={deck.bottom_line.body} />
        </Section>
      )}
      {deck.missing_info && deck.missing_info.body.items.length > 0 && (
        <Section title="Still to check" lit={lit.has("missing_info")}>
          <MissingInfo body={deck.missing_info.body} />
        </Section>
      )}
      {deck.ledger && deck.ledger.body.rows.length > 0 && (
        <Section title="Day by day" lit={lit.has("ledger")}>
          <Ledger body={deck.ledger.body} />
        </Section>
      )}
    </div>
  );
}

/** Three figures, not three identical boxes. Whichever one the month turns on
 *  is the one that gets the size and the colour; the other two sit under it. */
function Figures({ deck }: { deck: Deck }) {
  const cash = deck.cash_position?.body;
  const plan = deck.bottom_line!.body;
  if (!cash) return null;
  // The shortfall is the tightest point with its sign flipped — the same number
  // under two names — so only ever one of them earns a slot.
  const short = plan.still_short.paise > 0;
  return (
    <dl className="flex flex-wrap items-baseline gap-x-10 gap-y-4 border-y py-3.5">
      <Figure label="In hand now" amount={cash.opening} />
      {short ? (
        <Figure label="Still short" amount={plan.still_short} hero bad />
      ) : (
        <Figure label="Tightest point" amount={cash.lowest} hero />
      )}
      <Figure label="At the end" amount={cash.closing} />
    </dl>
  );
}

function Figure({
  label,
  amount,
  hero,
  bad,
}: {
  label: string;
  amount: Amount;
  hero?: boolean;
  bad?: boolean;
}) {
  return (
    <div>
      <dt className="text-muted-foreground text-[11px] font-medium tracking-wider uppercase">
        {label}
      </dt>
      <dd
        className={cn(
          "mt-0.5 font-semibold tabular-nums",
          hero ? "text-[1.6rem] leading-none" : "text-lg leading-none",
          bad ? "text-destructive" : amount.paise < 0 && "text-destructive",
        )}
      >
        <PopNumber text={rupees(amount)} />
      </dd>
    </div>
  );
}

type TabId = "told" | "working";

const TABS: { id: TabId; label: string; cards: CardId[] }[] = [
  { id: "told", label: "What you told me", cards: ["income", "essentials", "obligations", "optionals"] },
  // Short, because two tabs have to fit beside each other in a workspace that
  // is only a few hundred pixels wide on a laptop. The section inside says the
  // long version.
  { id: "working", label: "How it adds up", cards: ["bottom_line", "missing_info", "ledger"] },
];

/** A pill that travels between tabs rather than an underline that jumps. The
 *  first paint writes the position with the transition suspended, so the pill
 *  does not slide in from the left edge on load.
 *
 *  Two tabs, and neither moves on its own. The five that mirrored the server's
 *  card list were the data model showing through, and following the
 *  conversation meant the panel changed under whoever was reading it. */
function Tabs({
  open,
  lit,
  onPick,
}: {
  open: TabId;
  lit: Set<CardId>;
  onPick: (id: TabId) => void;
}) {
  const bar = useRef<HTMLDivElement>(null);
  const pill = useRef<HTMLSpanElement>(null);
  const settled = useRef(false);

  useLayoutEffect(() => {
    const active = bar.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!active || !pill.current) return;
    if (!settled.current) pill.current.dataset.first = "true";
    pill.current.style.transform = `translateX(${active.offsetLeft}px)`;
    pill.current.style.width = `${active.offsetWidth}px`;
    if (!settled.current) {
      void pill.current.offsetWidth;
      delete pill.current.dataset.first;
      settled.current = true;
    }
  }, [open]);

  return (
    <div ref={bar} role="tablist" className="t-tabs bg-muted/60 min-w-0 self-start rounded-lg p-1">
      <span ref={pill} className="t-tabs-pill" aria-hidden="true" />
      {TABS.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === open}
          onClick={() => onPick(tab.id)}
          className={cn(
            "t-tab rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors",
            tab.id === open ? "font-medium" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
          {tab.id !== open && tab.cards.some((id) => lit.has(id)) && (
            <span className="bg-foreground/50 ml-1.5 inline-block size-1.5 rounded-full align-middle" />
          )}
        </button>
      ))}
    </div>
  );
}
