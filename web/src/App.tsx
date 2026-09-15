import { ConnectButton } from "@/components/pipecat/connect-button";
import { Conversation } from "@/components/pipecat/conversation";
import { UserAudioControl } from "@/components/pipecat/user-audio-control";
import { usePipecatClient } from "@pipecat-ai/client-react";
import { useEffect, useState } from "react";
import { CONNECT } from "./client";

type Health = {
  status: string;
  providers: Record<string, string>;
  missing_env: string[];
};

export function App() {
  const client = usePipecatClient();
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  const missing = health?.missing_env ?? [];

  // The button would otherwise call client.connect() with no arguments, which
  // has no idea where the room is. Starting the call is the server's job.
  async function startCall() {
    setError(null);
    try {
      await client?.connect(CONNECT);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="mx-auto flex h-dvh max-w-2xl flex-col gap-4 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">FinVoice</h1>
        <p className="text-muted-foreground text-sm">
          Thirty-day financial planning, by voice.
        </p>
      </header>

      {missing.length > 0 && (
        <p className="border-destructive/40 text-destructive rounded-lg border p-3 text-sm">
          Missing environment variables: {missing.join(", ")}. Copy <code>.env.example</code> to{" "}
          <code>.env</code> and fill them in.
        </p>
      )}
      {error && <p className="text-destructive text-sm">{error}</p>}

      <section className="min-h-0 flex-1 overflow-y-auto rounded-lg border p-4">
        <Conversation />
      </section>

      <div className="flex items-center gap-3">
        <ConnectButton onConnect={startCall} disabled={missing.length > 0} />
        <UserAudioControl />
      </div>

      {health && (
        <footer className="text-muted-foreground flex flex-wrap gap-4 text-xs">
          {Object.entries(health.providers).map(([name, value]) => (
            <span key={name}>
              {name}: {value}
            </span>
          ))}
        </footer>
      )}
    </main>
  );
}
