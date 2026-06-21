"use client";

import { useState, useTransition } from "react";

type Props = {
  initialStep: number;
  initialBrandName: string;
  initialDescription: string;
  suggestedAliases: string[];
  completed: boolean;
};

export default function WizardClient(p: Props) {
  // We let setupStep advance locally as the user moves; on reload the server
  // is authoritative (page.tsx re-reads brand_config.setup_step). That way
  // the UI is responsive without lying about persisted state.
  const [step, setStep] = useState<number>(Math.max(1, p.initialStep));
  const [pending, start] = useTransition();
  const [status, setStatus] = useState<string | null>(null);

  if (p.completed) {
    return (
      <section style={card}>
        <h2>Setup complete</h2>
        <p>You can edit the brand config below if anything needs updating.</p>
      </section>
    );
  }

  return (
    <div>
      {step === 1 && (
        <Step1
          initialBrandName={p.initialBrandName}
          initialDescription={p.initialDescription}
          suggestedAliases={p.suggestedAliases}
          onNext={() => setStep(2)}
          start={start}
          pending={pending}
          setStatus={setStatus}
        />
      )}
      {step === 2 && <Step2 onNext={() => setStep(3)} start={start} pending={pending} setStatus={setStatus} />}
      {step === 3 && <Step3 onNext={() => setStep(4)} start={start} pending={pending} setStatus={setStatus} />}
      {step === 4 && <Step4 onNext={() => setStep(5)} start={start} pending={pending} setStatus={setStatus} />}
      {step === 5 && <Step5 onNext={() => setStep(6)} start={start} pending={pending} setStatus={setStatus} />}
      {step === 6 && <Step6 onNext={() => setStep(7)} start={start} pending={pending} setStatus={setStatus} />}
      {step === 7 && <Step7 start={start} pending={pending} setStatus={setStatus} />}
      {status && <p style={{ marginTop: 12 }}>{status}</p>}
    </div>
  );
}

type StepProps = {
  onNext: () => void;
  start: React.TransitionStartFunction;
  pending: boolean;
  setStatus: (s: string | null) => void;
};

function Step1({
  initialBrandName,
  initialDescription,
  suggestedAliases,
  onNext,
  start,
  pending,
  setStatus,
}: StepProps & {
  initialBrandName: string;
  initialDescription: string;
  suggestedAliases: string[];
}) {
  const [brandName, setBrandName] = useState(initialBrandName);
  const [description, setDescription] = useState(initialDescription);
  const [aliases, setAliases] = useState<string>(
    (suggestedAliases.length ? suggestedAliases : [""]).join(", "),
  );
  const submit = () =>
    start(async () => {
      setStatus("Saving brand basics…");
      const aliasList = aliases.split(",").map((a) => a.trim()).filter(Boolean);
      const res = await fetch("/api/wizard/step1", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brandName, description, aliases: aliasList }),
      });
      if (res.ok) {
        setStatus("Step 1 saved.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>1. Brand basics</h2>
      <label style={muted}>Brand name</label>
      <input style={input} value={brandName} onChange={(e) => setBrandName(e.target.value)} />
      <label style={muted}>Description</label>
      <textarea
        style={{ ...input, height: 80 }}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <label style={muted}>Aliases (comma-separated)</label>
      <input style={input} value={aliases} onChange={(e) => setAliases(e.target.value)} />
      <button style={btn} disabled={pending} onClick={submit}>
        {pending ? "Saving…" : "Save & continue"}
      </button>
    </section>
  );
}

function Step2({ onNext, start, pending, setStatus }: StepProps) {
  const [rows, setRows] = useState<Array<{ name: string; aliases: string }>>([
    { name: "", aliases: "" },
    { name: "", aliases: "" },
    { name: "", aliases: "" },
  ]);
  const submit = () =>
    start(async () => {
      const competitors = rows
        .filter((r) => r.name.trim())
        .map((r) => ({
          name: r.name.trim(),
          aliases: r.aliases.split(",").map((a) => a.trim()).filter(Boolean),
        }));
      const res = await fetch("/api/wizard/step2", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ competitors }),
      });
      if (res.ok) {
        setStatus("Step 2 saved.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>2. Competitors (3-10)</h2>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <input
            style={input}
            placeholder="Competitor name"
            value={r.name}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
          />
          <input
            style={input}
            placeholder="Aliases (comma-separated)"
            value={r.aliases}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, aliases: e.target.value } : x)))}
          />
        </div>
      ))}
      <button style={btnSecondary} onClick={() => setRows([...rows, { name: "", aliases: "" }])}>
        + Add competitor
      </button>
      <button style={btn} disabled={pending} onClick={submit}>
        {pending ? "Saving…" : "Save & continue"}
      </button>
    </section>
  );
}

function Step3({ onNext, start, pending, setStatus }: StepProps) {
  const [queries, setQueries] = useState<string[]>([]);
  const [text, setText] = useState("");
  const suggest = () =>
    start(async () => {
      setStatus("Asking Claude for suggestions…");
      const res = await fetch("/api/wizard/suggest-queries", { method: "POST" });
      const json = await res.json();
      if (res.ok) {
        setQueries([...queries, ...(json.queries as string[])]);
        setStatus(`Got ${json.queries.length} suggested queries.`);
      } else {
        setStatus(`Error: ${json.error}`);
      }
    });
  const submit = () =>
    start(async () => {
      const all = [...queries, ...text.split("\n").map((q) => q.trim()).filter(Boolean)];
      const res = await fetch("/api/wizard/step3", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queries: all }),
      });
      if (res.ok) {
        setStatus("Step 3 saved.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>3. Tracked queries</h2>
      <button style={btnSecondary} disabled={pending} onClick={suggest}>
        {pending ? "Working…" : "Suggest with Claude"}
      </button>
      {queries.length > 0 && (
        <ul>
          {queries.map((q, i) => (
            <li key={i}>
              {q}{" "}
              <button style={miniBtn} onClick={() => setQueries(queries.filter((_, j) => j !== i))}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <label style={muted}>Add your own (one per line)</label>
      <textarea style={{ ...input, height: 100 }} value={text} onChange={(e) => setText(e.target.value)} />
      <button style={btn} disabled={pending} onClick={submit}>
        {pending ? "Saving…" : "Save & continue"}
      </button>
    </section>
  );
}

function Step4({ onNext, start, pending, setStatus }: StepProps) {
  const [seeds, setSeeds] = useState("");
  const [expanded, setExpanded] = useState<string[]>([]);
  const discover = () =>
    start(async () => {
      const seedList = seeds.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      const res = await fetch("/api/wizard/discover-subs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seeds: seedList }),
      });
      const json = await res.json();
      if (res.ok) {
        setExpanded(json.subs);
        setStatus(`Discovered ${json.subs.length} subs.`);
      } else {
        setStatus(`Error: ${json.error}`);
      }
    });
  const submit = () =>
    start(async () => {
      const res = await fetch("/api/wizard/step4", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approvedSubs: expanded }),
      });
      if (res.ok) {
        setStatus("Step 4 saved.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>4. Seed subreddits</h2>
      <label style={muted}>Seed subs (comma or newline)</label>
      <textarea style={{ ...input, height: 60 }} value={seeds} onChange={(e) => setSeeds(e.target.value)} />
      <button style={btnSecondary} disabled={pending} onClick={discover}>
        {pending ? "Working…" : "Discover adjacent"}
      </button>
      {expanded.length > 0 && (
        <ul>
          {expanded.map((s) => (
            <li key={s}>r/{s}</li>
          ))}
        </ul>
      )}
      <button style={btn} disabled={pending || expanded.length === 0} onClick={submit}>
        {pending ? "Saving…" : "Save & continue"}
      </button>
    </section>
  );
}

function Step5({ onNext, start, pending, setStatus }: StepProps) {
  const [add, setAdd] = useState("");
  const submit = () =>
    start(async () => {
      const addList = add.split("\n").map((a) => a.trim()).filter(Boolean);
      const res = await fetch("/api/wizard/step5", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ add: addList, remove: [] }),
      });
      if (res.ok) {
        setStatus("Step 5 saved.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>5. Disclosure phrases</h2>
      <p style={muted}>
        Defaults are loaded. Add brand-specific phrases below (one per line) —
        they layer on top of the defaults.
      </p>
      <textarea style={{ ...input, height: 100 }} value={add} onChange={(e) => setAdd(e.target.value)} />
      <button style={btn} disabled={pending} onClick={submit}>
        {pending ? "Saving…" : "Save & continue"}
      </button>
    </section>
  );
}

function Step6({ onNext, start, pending, setStatus }: StepProps) {
  const [email, setEmail] = useState("");
  const submit = () =>
    start(async () => {
      const res = await fetch("/api/wizard/step6", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setStatus("Step 6 saved — invite sent.");
        onNext();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });
  return (
    <section style={card}>
      <h2>6. Invite first teammate</h2>
      <input
        style={input}
        type="email"
        placeholder="teammate@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <button style={btn} disabled={pending} onClick={submit}>
        {pending ? "Sending…" : "Invite & continue"}
      </button>
    </section>
  );
}

function Step7({ start, pending, setStatus }: Omit<StepProps, "onNext">) {
  const [result, setResult] = useState<unknown>(null);
  const run = () =>
    start(async () => {
      setStatus("Running smoke test…");
      const res = await fetch("/api/wizard/step7", { method: "POST" });
      const json = await res.json();
      setResult(json.result);
      setStatus("Smoke test complete.");
    });
  const confirm = () =>
    start(async () => {
      const res = await fetch("/api/wizard/step7?confirm=1", { method: "POST" });
      if (res.ok) setStatus("Setup complete!");
    });
  return (
    <section style={card}>
      <h2>7. Smoke test</h2>
      <button style={btnSecondary} disabled={pending} onClick={run}>
        {pending ? "Running…" : "Run smoke test"}
      </button>
      {result !== null && (
        <pre style={{ background: "#0b0b0d", padding: 12, borderRadius: 6, overflow: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      <button style={btn} disabled={pending || result === null} onClick={confirm}>
        Looks right — mark setup complete
      </button>
    </section>
  );
}

const card: React.CSSProperties = { background: "#16161a", padding: 16, borderRadius: 8, margin: "16px 0" };
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 13, display: "block", margin: "8px 0 4px" };
const btn: React.CSSProperties = {
  padding: "8px 14px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
  marginTop: 12,
  marginRight: 8,
};
const btnSecondary: React.CSSProperties = { ...btn, background: "#2a2a30" };
const miniBtn: React.CSSProperties = { ...btnSecondary, padding: "2px 6px", marginLeft: 6, marginTop: 0 };
const input: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  background: "#0b0b0d",
  color: "#e7e7ea",
  border: "1px solid #2a2a30",
  borderRadius: 6,
  marginBottom: 4,
};
