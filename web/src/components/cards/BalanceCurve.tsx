/** The running balance across the thirty days, with the zero line drawn.
 *
 * This is the one picture the product exists to show: the money is fine, and
 * then on a particular day it is not. A strip of thirty equal boxes says "here
 * are thirty days"; the curve says "here is where it breaks", which is the
 * sentence the user came for.
 *
 * It is drawn from the ledger rather than the calendar so every point carries
 * what landed on it. A balance that climbs for a fortnight with nothing marked
 * on it is a chart that raises a question it cannot answer — the first thing
 * anyone asks of this curve is "why is it going up there", and the answer is
 * usually income recorded as spread, trickling in daily against no outgoings.
 * Days where something actually lands get a dot; the rest is drift.
 *
 * There is no y-axis on purpose. Tick labels would mean dividing paise into
 * rupees in the browser, and the rule this whole design exists to keep is that
 * no figure is computed on this side. Every amount shown is the server's own
 * `text`; the only arithmetic here is turning paise into pixels.
 */

import { Area, AreaChart, CartesianGrid, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts";

import type { Bodies, Entry } from "@/cards";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";

import { monthOf, rupees, shortDate } from "./parts";

const CONFIG = {
  balance: { label: "Balance", color: "var(--foreground)" },
} satisfies ChartConfig;

type Point = {
  label: string;
  month: string;
  paise: number;
  text: string;
  entries: Entry[];
};

export function BalanceCurve({
  ledger,
  calendar,
}: {
  ledger: Bodies["ledger"];
  calendar: Bodies["calendar"];
}) {
  const rows = ledger.rows;
  if (rows.length < 2) return null;

  const data: Point[] = rows.map((row) => ({
    label: shortDate(row.on),
    month: monthOf(row.on),
    paise: row.closing.paise,
    text: rupees(row.closing),
    entries: row.entries,
  }));

  // A curve earns its space once the balance has moved on more than one day.
  // Before that it is a flat line with a single step in it, which takes two
  // hundred pixels to say what the figures underneath already said.
  const moves = data.filter((d, i) => i > 0 && d.paise !== data[i - 1].paise).length;
  if (moves < 2) return null;

  const high = Math.max(...data.map((d) => d.paise), 0);
  const low = Math.min(...data.map((d) => d.paise), 0);
  // Where zero sits between the top and bottom of the plot. Two gradient stops
  // at the same offset make the fill and stroke change colour exactly at the
  // zero line rather than somewhere near it.
  const split = high / (high - low);
  // Only when there is an actual crossing to draw. A balance that never goes
  // negative puts both stops on offset 1, and anything sitting at exactly zero
  // then lands on the far stop and paints itself red — the chart announcing a
  // shortfall on a month where nothing has been recorded yet.
  const crosses = low < 0 && high > 0;
  const ink = low < 0 ? "var(--destructive)" : "var(--foreground)";

  // The server already decided which days are short; this never re-derives it.
  const firstShort = calendar.days.findIndex((day) => day.negative);
  const crossing = data.findIndex((d, i) => i > 0 && d.month !== data[i - 1].month);

  return (
    <ChartContainer config={CONFIG} className="h-48 w-full">
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="balance-fill" x1="0" y1="0" x2="0" y2="1">
            {crosses ? (
              <>
                <stop offset={0} stopColor="var(--foreground)" stopOpacity={0.18} />
                <stop offset={split} stopColor="var(--foreground)" stopOpacity={0.02} />
                <stop offset={split} stopColor="var(--destructive)" stopOpacity={0.12} />
                <stop offset={1} stopColor="var(--destructive)" stopOpacity={0.32} />
              </>
            ) : (
              <>
                <stop offset={0} stopColor={ink} stopOpacity={low < 0 ? 0.04 : 0.18} />
                <stop offset={1} stopColor={ink} stopOpacity={low < 0 ? 0.3 : 0.02} />
              </>
            )}
          </linearGradient>
          <linearGradient id="balance-stroke" x1="0" y1="0" x2="0" y2="1">
            {crosses ? (
              <>
                <stop offset={split} stopColor="var(--foreground)" />
                <stop offset={split} stopColor="var(--destructive)" />
              </>
            ) : (
              <stop offset={0} stopColor={ink} />
            )}
          </linearGradient>
        </defs>

        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tickMargin={10}
          minTickGap={44}
          className="text-[11px]"
          stroke="var(--muted-foreground)"
        />
        <YAxis hide domain={[Math.min(0, low), Math.max(0, high)]} />

        <ChartTooltip cursor={{ stroke: "var(--border)" }} content={<DayTooltip />} />

        {crossing > 0 && (
          <ReferenceLine
            x={data[crossing].label}
            stroke="var(--muted-foreground)"
            strokeDasharray="2 4"
            strokeOpacity={0.6}
            label={{
              value: data[crossing].month,
              position: "insideTopLeft",
              fontSize: 11,
              fill: "var(--muted-foreground)",
            }}
          />
        )}
        <ReferenceLine
          y={0}
          stroke="var(--muted-foreground)"
          strokeDasharray="4 4"
          strokeOpacity={0.7}
        />

        <Area
          dataKey="paise"
          type="linear"
          fill="url(#balance-fill)"
          stroke="url(#balance-stroke)"
          strokeWidth={2}
          dot={<EventDot />}
          activeDot={{ r: 4, fill: "var(--foreground)", stroke: "var(--card)", strokeWidth: 2 }}
          isAnimationActive={false}
        />

        {firstShort > 0 && (
          <ReferenceDot
            x={data[firstShort].label}
            y={data[firstShort].paise}
            r={4}
            fill="var(--destructive)"
            stroke="var(--card)"
            strokeWidth={2}
          />
        )}
      </AreaChart>
    </ChartContainer>
  );
}

/** A mark only where something landed. Spread income trickles onto all thirty
 *  days, so dotting every point marks nothing at all — what the eye needs is
 *  the days that have a cause worth naming. */
function EventDot(props: { cx?: number; cy?: number; payload?: Point }) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined || !payload) return null;
  if (!hasEvent(payload.entries)) return null;
  return <circle cx={cx} cy={cy} r={2.5} fill="var(--foreground)" opacity={0.55} />;
}

/** A single small amount on its own is a spread fact drifting; anything else is
 *  an event. The threshold is a display decision, not a financial one. */
function hasEvent(entries: Entry[]): boolean {
  if (entries.length === 0) return false;
  if (entries.length > 1) return true;
  return Math.abs(entries[0].amount.paise) >= 100_000;
}

function DayTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="bg-popover text-popover-foreground min-w-44 rounded-lg border px-2.5 py-2 text-xs shadow-md">
      <div className="text-muted-foreground mb-1.5">{point.label}</div>
      {point.entries.length === 0 ? (
        <div className="text-muted-foreground mb-1.5 italic">Nothing lands</div>
      ) : (
        <ul className="mb-1.5 space-y-0.5">
          {point.entries.map((entry) => (
            <li key={`${entry.label}:${entry.amount.paise}`} className="flex justify-between gap-4">
              <span className="truncate">{entry.label}</span>
              <span className={entry.amount.paise < 0 ? "text-destructive tabular-nums" : "tabular-nums"}>
                {rupees(entry.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex justify-between gap-4 border-t pt-1.5 font-medium">
        <span>Balance</span>
        <span className={point.paise < 0 ? "text-destructive tabular-nums" : "tabular-nums"}>
          {point.text}
        </span>
      </div>
    </div>
  );
}
