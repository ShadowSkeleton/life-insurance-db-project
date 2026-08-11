// Jingrui Feng (jf4446) - Part 4 refresh controls and source lineage
"use client";

import { useEffect, useState } from "react";
import { Clock3, Database, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { number } from "@/lib/pricing";
import type { DataSourceStateRow, RateVersionRow, RefreshRunRow } from "@/lib/types";

type GateComparison = { baseline: number | null; new: number; minimum?: number | null; passed: boolean };
type GateOutcome = {
  passed: boolean;
  baseline_recorded?: boolean;
  reason?: string;
  auc?: GateComparison;
  wonder?: { values: Record<string, number>; passed: boolean };
  ssa_violations?: GateComparison;
};
type RefreshOutcome = {
  outcome: "no_source_change" | "retrained_gate_passed" | "retraining_gate_failed";
  retraining: { retrained: boolean; observed_hash: string; byte_size: number; gate: GateOutcome };
  gate: GateOutcome;
  runId: number | null;
  rateVersionId: number | null;
};
type History = { versions: RateVersionRow[]; runs: RefreshRunRow[]; sourceStates: DataSourceStateRow[]; message?: string };

const hash = (value: string | null) => value ? `${value.slice(0, 12)}…` : "—";
const amount = (value: number | null) => value === null ? "—" : number.format(value);

function GateCard({ outcome }: { outcome: RefreshOutcome }) {
  const gate = outcome.gate;
  if (outcome.outcome === "no_source_change") return <Card className="border-l-4 border-active p-5"><p className="font-semibold text-ink">No source change detected</p><p className="mt-1 text-sm text-muted">Hash {hash(outcome.retraining.observed_hash)} matched the latest recorded source state. The refresh ran without retraining.</p></Card>;
  if (!gate.auc || !gate.wonder || !gate.ssa_violations) return null;
  return <Card className={`border-l-4 p-5 ${gate.passed ? "border-active" : "border-old"}`}>
    <div className="flex items-center gap-2"><ShieldCheck size={18} className={gate.passed ? "text-active" : "text-old"} /><h2 className="font-display text-2xl text-slate">Validation gate {gate.passed ? "passed" : "failed"}</h2></div>
    <p className="mt-2 text-sm text-muted">{gate.baseline_recorded ? "No prior baseline existed; this fit established it." : gate.passed ? "The new model met every relative comparison." : "The fit was retained for inspection, but the previous model and rate version remain in force."}</p>
    <dl className="nums mt-5 grid gap-4 text-sm md:grid-cols-3">
      <div><dt className="text-muted">AUC</dt><dd className="mt-1 font-semibold">baseline {gate.auc.baseline ?? "—"} → {gate.auc.new} {gate.auc.minimum !== undefined && <span className="text-muted">(minimum {gate.auc.minimum})</span>}</dd></div>
      <div><dt className="text-muted">WONDER direction</dt><dd className="mt-1 font-semibold">{Object.entries(gate.wonder.values).map(([sex, value]) => `${sex}: ${value}`).join(" · ")}</dd></div>
      <div><dt className="text-muted">SSA ordering violations</dt><dd className="mt-1 font-semibold">baseline {gate.ssa_violations.baseline ?? "—"} → {gate.ssa_violations.new}</dd></div>
    </dl>
  </Card>;
}

export default function RepricePage() {
  const [history, setHistory] = useState<History | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");
  const [output, setOutput] = useState("");
  const [outcome, setOutcome] = useState<RefreshOutcome | null>(null);
  const [cohort, setCohort] = useState("2023");
  const [loadingFactor, setLoadingFactor] = useState("1.50");

  async function load() {
    setLoading(true);
    try {
      const response = await fetch("/api/reprice/history");
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      setHistory(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rate history could not be read.");
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function refresh() {
    setRunning(true); setMessage(""); setOutput(""); setOutcome(null);
    try {
      const response = await fetch("/api/reprice", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ wonderCohortSourceYear: Number(cohort), loadingFactor: Number(loadingFactor) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      setMessage(data.message);
      setOutput(data.output ?? "");
      setOutcome(data as RefreshOutcome);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The refresh did not complete.");
    } finally { setRunning(false); }
  }

  return <div className="space-y-7">
    <div className="grid gap-5 border-b border-slate/15 pb-7 md:grid-cols-[1fr_auto]"><div><p className="font-mono text-xs font-semibold tracking-[0.16em] text-active">UC-4 · PART 4 LINEAGE</p><h1 className="mt-2 font-display text-4xl text-slate md:text-5xl">Rate versions</h1><p className="mt-3 max-w-2xl text-muted">The refresh job records source lineage before publishing a new rate book. It never updates Contract.</p></div></div>
    <Card className="p-5"><div className="grid gap-4 md:grid-cols-[1fr_220px_auto]"><label className="text-sm font-semibold text-ink">Mortality data source<select className="mt-2 block w-full border border-slate/20 bg-white px-3 py-2 outline-none focus:border-active focus:ring-2 focus:ring-active/20" value={cohort} onChange={(event) => setCohort(event.target.value)}><option value="2023">2022–2024 mortality cohort</option><option value="2024">2018–2024 pooled mortality cohort</option></select></label><label className="text-sm font-semibold text-ink">Expense and margin loading<input className="nums mt-2 block w-full border border-slate/20 bg-white px-3 py-2 outline-none focus:border-active focus:ring-2 focus:ring-active/20" type="number" min="0.01" step="0.01" value={loadingFactor} onChange={(event) => setLoadingFactor(event.target.value)} /></label><div className="self-end"><Button onClick={refresh} disabled={running} className="gap-2"><RefreshCw size={16} className={running ? "animate-spin" : ""} />{running ? "Publishing…" : "Run local refresh"}</Button></div></div><p className="mt-4 text-sm leading-6 text-muted">The page reports no source change, a gate-passing retrain, or a gate-failing retrain that retains the prior model.</p></Card>
    {outcome && <GateCard outcome={outcome} />}
    {message && <Card className="fade-in p-5"><p className="font-semibold text-ink">{message}</p>{output && <pre className="nums mt-3 max-h-64 overflow-auto bg-paper p-3 text-xs text-muted">{output}</pre>}</Card>}
    <section><div className="mb-3 flex items-center gap-2"><Clock3 size={18} className="text-active" /><h2 className="font-display text-3xl text-slate">Rate book ledger</h2></div>{loading ? <Card className="p-6 text-muted">Loading version history…</Card> : history && <Card className="overflow-x-auto"><table className="w-full min-w-[700px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Version</th><th className="px-5 py-3">Effective</th><th className="px-5 py-3">Expiry</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Pinned contracts</th></tr></thead><tbody>{history.versions.map((version) => <tr key={version.RateVersionID} className={version.Status === "active" ? "bg-[#E7F5F5]" : "border-t border-slate/10"}><td className="nums px-5 py-4 font-semibold text-ink">v{version.RateVersionID}</td><td className="nums px-5 py-4">{version.EffectiveDate}</td><td className="nums px-5 py-4">{version.ExpiryDate ?? "Current"}</td><td className="px-5 py-4">{version.Status}</td><td className="nums px-5 py-4 text-right">{number.format(version.PinnedContracts)}</td></tr>)}</tbody></table></Card>}</section>
    <section><h2 className="mb-3 font-display text-3xl text-slate">Refresh audit trail</h2>{history && <Card className="overflow-x-auto"><table className="w-full min-w-[1080px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Run</th><th className="px-5 py-3">Started</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Retrained</th><th className="px-5 py-3">Source hash</th><th className="px-5 py-3 text-right">Bytes</th><th className="px-5 py-3">Published version</th></tr></thead><tbody>{history.runs.map((run) => <tr key={run.RunID} className="border-t border-slate/10"><td className="nums px-5 py-4">#{run.RunID}</td><td className="nums px-5 py-4">{run.StartedAt}</td><td className="px-5 py-4">{run.Status}</td><td className="px-5 py-4">{run.Retrained ? "Yes" : "No"}</td><td className="nums px-5 py-4">{hash(run.ObservedHash)}</td><td className="nums px-5 py-4 text-right">{amount(run.ObservedByteSize)}</td><td className="nums px-5 py-4">{run.NewRateVersionID ? `v${run.NewRateVersionID}` : "—"}</td></tr>)}</tbody></table></Card>}</section>
    <section><div className="mb-3 flex items-center gap-2"><Database size={18} className="text-active" /><h2 className="font-display text-3xl text-slate">Source-state lineage</h2></div>{history && <Card className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">State</th><th className="px-5 py-3">Observed</th><th className="px-5 py-3">Run</th><th className="px-5 py-3">Source path</th><th className="px-5 py-3">SHA-256</th><th className="px-5 py-3 text-right">Bytes</th></tr></thead><tbody>{history.sourceStates.map((state) => <tr key={state.SourceStateID} className="border-t border-slate/10"><td className="nums px-5 py-4">#{state.SourceStateID}</td><td className="nums px-5 py-4">{state.ObservedAt}</td><td className="nums px-5 py-4">#{state.ObservedByRunID}</td><td className="max-w-sm truncate px-5 py-4" title={state.SourcePath}>{state.SourcePath}</td><td className="nums px-5 py-4" title={state.ContentHash}>{hash(state.ContentHash)}</td><td className="nums px-5 py-4 text-right">{amount(state.ByteSize)}</td></tr>)}</tbody></table>{history.sourceStates.length === 0 && <p className="p-5 text-sm text-muted">No source state has been published yet.</p>}</Card>}</section>
  </div>;
}
