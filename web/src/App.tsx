import { ConnectButton } from "@/components/pipecat/connect-button";
import { Conversation } from "@/components/pipecat/conversation";
import { UserAudioControl } from "@/components/pipecat/user-audio-control";
import { AudioVisualizerWave } from "@/components/pipecat/audio-visualizer-wave";
import { Workspace } from "@/components/cards/Workspace";
import { shortDate } from "@/components/cards/parts";
import { cn } from "@/lib/utils";
import { usePipecatClient } from "@pipecat-ai/client-react";
import { CheckIcon } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { CONNECT } from "./client";
import { useCallState, type CallState } from "./useCallState";
import { useCards } from "./useCards";

type Health = {
  status: string;
  providers: Record<string, string>;
  missing_env: string[];
  /** Seams pointed at a provider nothing can build — a typo in a name, not a
   *  missing key. Reported here rather than raised on the first call. */
  misconfigured: string[];
};

export function App() {
  const client = usePipecatClient();
  const { deck, lit } = useCards();
  const state = useCallState();
  const [transcript, setTranscript] = useState(false);
  const [nerds, setNerds] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  const missing = health?.missing_env ?? [];
  const misconfigured = health?.misconfigured ?? [];
  const blocked = missing.length > 0 || misconfigured.length > 0;

  // The button would otherwise call client.connect() with no arguments, which
  // has no idea where the room is. Starting the call is the server's job, and
  // startBotAndConnect is the call that says so — connect() with an endpoint is
  // deprecated and warns in the console.
  async function startCall() {
    setError(null);
    try {
      await client?.startBotAndConnect(CONNECT);
    } catch (e) {
      setError(String(e));
    }
  }

  // A fixed-height app shell only where there is height to divide. Below `lg`
  // the same shell split a short viewport three ways and handed the workspace a
  // third of it, which is how the card ended up as a clipped sliver with its own
  // scrollbar. Under that width the page scrolls instead.
  return (
    <main className="mx-auto flex min-h-dvh max-w-6xl flex-col gap-4 p-4 sm:p-6 lg:h-dvh">
      <header className="flex shrink-0 flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-lg tracking-tight">FinVoice</h1>
          <p className="text-muted-foreground text-sm tabular-nums">
            {windowSpoken(deck) ?? "thirty days, by voice"}
          </p>
        </div>
        <div className="text-muted-foreground flex shrink-0 items-center gap-4 text-xs">
          <Check on={transcript} onChange={setTranscript}>
            Transcript
          </Check>
          {/* One switch for everything a normal user has no use for: which
              models are wired up, and the function-call rows in the transcript.
              Both are the same claim — that the numbers came from a tool — and
              hiding half of it behind a different control helped nobody. */}
          <Check on={nerds} onChange={setNerds}>
            Stats for nerds
          </Check>
        </div>
      </header>

      {misconfigured.length > 0 && (
        <div className="border-destructive/40 text-destructive shrink-0 rounded-lg border p-3 text-sm">
          <p className="font-medium">This configuration cannot place a call.</p>
          <ul className="mt-1 space-y-0.5 font-mono text-xs">
            {misconfigured.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      {missing.length > 0 && (
        <p className="border-destructive/40 text-destructive shrink-0 rounded-lg border p-3 text-sm">
          Missing environment variables: {missing.join(", ")}. Copy <code>.env.example</code> to{" "}
          <code>.env</code> and fill them in.
        </p>
      )}
      {error && <p className="text-destructive shrink-0 text-sm">{error}</p>}

      {/* The call on the left, the work on the right. The rail sits on the page
          itself and the work is raised onto a card — one depth strategy, and the
          orb keeps a fixed home rather than living in a strip under everything. */}
      <div
        className={cn(
          "grid gap-4 lg:min-h-0 lg:flex-1 lg:gap-6",
          // Narrower rails on a 13-inch screen, where three columns at 15rem
          // leave the workspace with less room than the things flanking it.
          transcript
            ? "lg:grid-cols-[13rem_minmax(0,1fr)_13rem] xl:grid-cols-[15rem_minmax(0,1fr)_16rem]"
            : "lg:grid-cols-[13rem_minmax(0,1fr)] xl:grid-cols-[15rem_minmax(0,1fr)]",
        )}
      >
        {/* One object, not three. A dark stage for the orb in both themes — the
            visualiser is made of light and washes out to nothing on paper — with
            the controls inside it rather than loose on the page below. The call
            is a single place on screen, and `dark` on the wrapper is what lets
            the shadcn controls inside it come out dark in a light theme. */}
        <aside className="dark text-foreground flex flex-col gap-4 rounded-2xl bg-[oklch(0.21_0.012_70)] p-4 max-lg:flex-row max-lg:items-center">
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 max-lg:flex-row max-lg:gap-5">
            <Orb state={state} />
            <Status state={state} />
          </div>
          <div className="flex shrink-0 flex-col gap-2 max-lg:flex-row max-lg:items-center">
            <ConnectButton onConnect={startCall} disabled={blocked} />
            {/* The kit's button group is `w-fit`, so it sat narrow and left of
                the full-width button above it. Widened to match, with the mic
                taking the slack and the device picker keeping its own size. */}
            <UserAudioControl className="lg:w-full lg:[&>button:first-child]:flex-1" />
          </div>
        </aside>

        <section className="bg-card rounded-2xl border p-5 shadow-[0_1px_2px_-1px_oklch(0_0_0/0.06),0_4px_12px_-6px_oklch(0_0_0/0.08)] max-lg:min-h-[34rem] sm:p-6 lg:min-h-0 dark:shadow-none">
          <Workspace deck={deck} lit={lit} />
        </section>

        {transcript && (
          <aside className="overflow-y-auto max-lg:max-h-80 max-lg:border-t max-lg:pt-4 lg:min-h-0">
            <Conversation noFunctionCalls={!nerds} assistantLabel="Agent" clientLabel="You" />
          </aside>
        )}
      </div>

      {nerds && health && (
        <p className="text-muted-foreground shrink-0 font-mono text-[11px]">
          {Object.entries(health.providers)
            .map(([name, value]) => `${name}=${value}`)
            .join("  ")}
        </p>
      )}
    </main>
  );
}

/** A checkbox, hand-rolled rather than pulled in: shadcn's needs another Radix
 *  package for a control with two states and no keyboard behaviour of its own
 *  that a button does not already have. */
function Check({
  on,
  onChange,
  children,
}: {
  on: boolean;
  onChange: (on: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        "hover:text-foreground flex items-center gap-1.5 transition-colors",
        on && "text-foreground",
      )}
    >
      <span
        className={cn(
          "grid size-3.5 shrink-0 place-items-center rounded-[4px] border transition-colors",
          on ? "bg-foreground border-foreground" : "border-muted-foreground/50",
        )}
      >
        {on && <CheckIcon className="text-background size-2.5" strokeWidth={3.5} />}
      </span>
      {children}
    </button>
  );
}

// Sized to clear the rail's padding at its narrowest (13rem) rather than to the
// widest layout, so the canvas never has to be scaled down mid-breakpoint.
const ORB = 160;

/** The call itself, as one object on screen.
 *
 * Pipecat's own shader visualiser rather than anything hand-rolled: silent and
 * speaking come off the audio track, so the orb rides the actual voice, and the
 * other two states are the documented overrides.
 */
function Orb({ state }: { state: CallState }) {
  // The canvas is nothing but motion, and the CSS rule that stills everything
  // else cannot reach a WebGL loop. The disc underneath stays, and the label
  // beside it already says whose turn it is.
  const still = useSyncExternalStore(subscribeMotion, () => MOTION.matches);
  return (
    <div
      className="relative grid shrink-0 place-items-center max-lg:size-20"
      style={{ width: ORB, height: ORB }}
    >
      {/* A bed under the canvas, so a browser without WebGL shows a quiet disc
          rather than a hole where the call should be. */}
      <span className="absolute size-[55%] rounded-full bg-white/5" />
      {!still && (
      <div className="max-lg:origin-center max-lg:scale-[0.45]">
        <AudioVisualizerWave
          participantType={state === "listening" ? "local" : "bot"}
          size={ORB}
          themeMode="dark"
          // One colour, always. Tinting per state made a teal orb on black,
          // which is every voice assistant ever shipped; lamplight amber belongs
          // to the paper-and-ink world the rest of the app lives in. Whose turn
          // it is is carried by the label and by the motion the component
          // already does — calm drift, a deep pulse while it thinks, and a body
          // that swells with speech.
          color="#F5A524"
          accentColor="#FFD79A"
          // Every one of these was above the component's own default, and the
          // shader's tone curve saturates hard: the result was a blown-out white
          // disc with a faint yellow bruise in the middle, which is not amber and
          // is not an orb. Back under the defaults, so the ink stays inside the
          // curve's responsive range and the colour survives.
          fill={0.5}
          hollow={0.34}
          core={0.12}
          glow={0.9}
          density={0.48}
          isConnecting={state === "joining"}
          isThinking={state === "thinking"}
        />
      </div>
      )}
    </div>
  );
}

const MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
function subscribeMotion(onChange: () => void) {
  MOTION.addEventListener("change", onChange);
  return () => MOTION.removeEventListener("change", onChange);
}

const LABEL: Record<CallState, string> = {
  offline: "Not connected",
  // Said from the moment the browser is in the room until the bot reports
  // ready. If the pipeline dies on setup this is where it stays, which is the
  // honest answer — the previous version said "Listening" to a dead call.
  joining: "Connecting",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  dropped: "Agent disconnected",
};

/** The label shimmers only while the agent is actually working, and swaps
 *  through a blur when it changes. The sizer holds the width of the longest
 *  state so the rail never reflows mid-sentence. */
function Status({ state }: { state: CallState }) {
  const label = LABEL[state];
  const live = state === "thinking" || state === "speaking";
  return (
    <span className="t-think text-sm font-medium">
      <span className="t-think-sizer">Agent disconnected</span>
      <span key={label} className="t-think-text" data-text={label} data-live={live}>
        {label}
      </span>
    </span>
  );
}

/** Which thirty days this call is about, read off the ledger the server sent.
 *  It is the one thing a user cannot infer and used to get wrong out loud: from
 *  the fifteenth, "the twentieth" is five days away and "the fifth" is twenty. */
function windowSpoken(deck: ReturnType<typeof useCards>["deck"]): string | null {
  const rows = deck.ledger?.body.rows;
  if (!rows || rows.length === 0) return null;
  return `${shortDate(rows[0].on)} – ${shortDate(rows[rows.length - 1].on)}`;
}
