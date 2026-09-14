import { useEffect, useState } from "react";

type Health = {
  status: string;
  providers: Record<string, string>;
  missing_env: string[];
  web_built: boolean;
};

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main>
      <h1>FinVoice</h1>
      <p className="tagline">Thirty-day financial planning, by voice.</p>

      {error && <p className="bad">Cannot reach the API: {error}</p>}
      {!health && !error && <p>Checking backend…</p>}

      {health && (
        <section>
          <h2>Backend</h2>
          <p className={health.status === "ok" ? "good" : "warn"}>status: {health.status}</p>
          <dl>
            {Object.entries(health.providers).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {health.missing_env.length > 0 && (
            <p className="warn">
              Missing environment variables: {health.missing_env.join(", ")}. Copy
              <code> .env.example </code> to <code> .env </code> and fill them in.
            </p>
          )}
        </section>
      )}

      <p className="phase">Voice conversation not yet wired up.</p>
    </main>
  );
}
