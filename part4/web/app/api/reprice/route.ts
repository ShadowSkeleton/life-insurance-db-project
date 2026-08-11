// Jingrui Feng (jf4446) - rate refresh endpoint
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";

let refreshRunning = false;

type RetrainingSummary = {
  retrained: boolean;
  observed_hash: string;
  byte_size: number;
  gate: Record<string, unknown>;
};

type RefreshSummary = {
  outcome: "no_source_change" | "retrained_gate_passed" | "retraining_gate_failed";
  run_id: number | null;
  rate_version_id: number | null;
  retraining: RetrainingSummary;
};

function readSummary(output: string): RefreshSummary | null {
  const line = output.split(/\r?\n/).findLast((item) => item.startsWith("PART4_REFRESH_RESULT="));
  if (!line) return null;
  try { return JSON.parse(line.slice("PART4_REFRESH_RESULT=".length)) as RefreshSummary; } catch { return null; }
}

export async function POST(request: Request) {
  if (refreshRunning) return NextResponse.json({ message: "A refresh is already running. Wait for it to finish." }, { status: 409 });
  refreshRunning = true;
  const projectRoot = path.resolve(process.cwd(), "..");
  const python = path.join(projectRoot, ".venv", "bin", "python");
  const script = path.join(projectRoot, "python", "run_rate_refresh.py");
  try {
    const body = await request.json().catch(() => ({}));
    const cohort = Number(body.wonderCohortSourceYear ?? 2023);
    const loading = Number(body.loadingFactor ?? 1.5);
    if (![2023, 2024].includes(cohort) || !Number.isFinite(loading) || loading <= 0) {
      return NextResponse.json({ message: "Select a supported mortality source and a positive loading factor." }, { status: 400 });
    }
    const result = await new Promise<{ output: string; status: number }>((resolve, reject) => {
      const child = spawn(python, [script, "--wonder-cohort-source-year", String(cohort), "--loading-factor", String(loading)], { cwd: projectRoot, env: process.env });
      let output = "";
      child.stdout.on("data", (chunk) => { output += chunk.toString(); });
      child.stderr.on("data", (chunk) => { output += chunk.toString(); });
      child.on("error", reject);
      child.on("close", (status) => resolve({ output, status: status ?? 1 }));
    });
    const summary = readSummary(result.output);
    if (summary?.outcome === "retraining_gate_failed") {
      return NextResponse.json({
        message: "Retraining completed, but the validation gate failed. The previous model and rate version were retained.",
        output: result.output, outcome: summary.outcome, retraining: summary.retraining,
        gate: summary.retraining.gate, runId: summary.run_id, rateVersionId: null,
      });
    }
    if (result.status !== 0) return NextResponse.json({ message: "The refresh did not publish a new rate version.", output: result.output }, { status: 500 });
    if (!summary) return NextResponse.json({ message: "The refresh completed without a Part 4 summary.", output: result.output }, { status: 500 });
    return NextResponse.json({
      message: summary.outcome === "no_source_change" ? "Refresh completed with no source change; no retraining occurred." : "Refresh completed after retraining passed the validation gate.",
      output: result.output, outcome: summary.outcome, retraining: summary.retraining,
      gate: summary.retraining.gate, runId: summary.run_id, rateVersionId: summary.rate_version_id,
    });
  } catch {
    return NextResponse.json({ message: "The refresh job could not start. Check the local Python environment." }, { status: 500 });
  } finally {
    refreshRunning = false;
  }
}
