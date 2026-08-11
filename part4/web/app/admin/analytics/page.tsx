// Jingrui Feng (jf4446) - analytics dashboard
"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Database, LineChart, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { number } from "@/lib/pricing";
import type {
  BRFSSPrevalenceRow, RateVersionRow, RefreshRunRow, SSAMortalityRow, WellnessParticipationRow,
} from "@/lib/types";

type Analytics = {
  versions: RateVersionRow[];
  prevalence: BRFSSPrevalenceRow[];
  mortality: SSAMortalityRow[];
  wellness: WellnessParticipationRow[];
  runs: RefreshRunRow[];
  message?: string;
};

const percent = new Intl.NumberFormat("en-US", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const rate = new Intl.NumberFormat("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 });

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch("/api/analytics");
        const result = await response.json() as Analytics;
        if (!response.ok) throw new Error(result.message);
        setData(result);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Analytics could not be read.");
      }
    })();
  }, []);

  const mortalityCurve = useMemo(() => {
    if (!data) return [];
    const byAge = new Map<string, { age: number; M?: SSAMortalityRow; F?: SSAMortalityRow }>();
    for (const row of data.mortality) {
      const age = Number(row.AgeBand);
      if (age % 10 !== 0 && age !== 99 && age !== 100) continue;
      const entry = byAge.get(row.AgeBand) ?? { age };
      entry[row.Gender] = row;
      byAge.set(row.AgeBand, entry);
    }
    return [...byAge.values()].sort((left, right) => left.age - right.age);
  }, [data]);

  if (message) return <Card className="border-l-4 border-old p-6 text-old">{message}</Card>;
  if (!data) return <Card className="p-6 text-muted">Loading Azure analytics…</Card>;

  return <div className="space-y-8">
    <div className="border-b border-slate/15 pb-7">
      <p className="font-mono text-xs font-semibold tracking-[0.16em] text-active">READ-ONLY ANALYTICS</p>
      <h1 className="mt-2 font-display text-4xl text-slate md:text-5xl">Rate book operations</h1>
      <p className="mt-3 max-w-3xl text-muted">This view reads the Azure SQL deployment only. It presents the refresh history, public-health staging measures, and wellness activity without changing any company data.</p>
    </div>

    <section className="grid gap-4 md:grid-cols-3">
      <Card className="p-5"><Database size={19} className="text-active" /><p className="mt-4 text-sm text-muted">Published rate versions</p><p className="nums mt-1 text-3xl font-semibold text-ink">{data.versions.length}</p></Card>
      <Card className="p-5"><RefreshCw size={19} className="text-active" /><p className="mt-4 text-sm text-muted">Successful refreshes</p><p className="nums mt-1 text-3xl font-semibold text-ink">{data.runs.filter((run) => run.Status === "success").length}</p></Card>
      <Card className="p-5"><Activity size={19} className="text-active" /><p className="mt-4 text-sm text-muted">Wellness activity events</p><p className="nums mt-1 text-3xl font-semibold text-ink">{number.format(data.wellness.reduce((sum, row) => sum + Number(row.QualifyingActivities), 0))}</p></Card>
    </section>

    <section><div className="mb-3 flex items-center gap-2"><Database size={18} className="text-active" /><h2 className="font-display text-3xl text-slate">Rate version history</h2></div><Card className="overflow-x-auto"><table className="w-full min-w-[650px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Version</th><th className="px-5 py-3">Effective</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Pinned contracts</th></tr></thead><tbody>{data.versions.map((version) => <tr key={version.RateVersionID} className={version.Status === "active" ? "bg-[#E7F5F5]" : "border-t border-slate/10"}><td className="nums px-5 py-4 font-semibold text-ink">v{version.RateVersionID}</td><td className="nums px-5 py-4">{version.EffectiveDate}</td><td className="px-5 py-4">{version.Status}</td><td className="nums px-5 py-4 text-right">{number.format(version.PinnedContracts)}</td></tr>)}</tbody></table></Card></section>

    <section><div className="mb-3 flex items-center gap-2"><LineChart size={18} className="text-active" /><h2 className="font-display text-3xl text-slate">BRFSS diabetes prevalence</h2></div><p className="mb-3 text-sm text-muted">Mean conditional diagnosed-diabetes prevalence by age band and gender from STG_BRFSS. The staging summary does not retain profile denominators, so this is an unweighted mean of its conditional rates.</p><Card className="overflow-x-auto"><table className="w-full min-w-[680px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Age band</th><th className="px-5 py-3">Gender</th><th className="px-5 py-3 text-right">Mean prevalence</th></tr></thead><tbody>{data.prevalence.map((row) => <tr key={`${row.AgeBand}-${row.Gender}`} className="border-t border-slate/10"><td className="nums px-5 py-3">{row.AgeBand}</td><td className="px-5 py-3">{row.Gender === "M" ? "Male" : "Female"}</td><td className="nums px-5 py-3 text-right">{percent.format(row.MeanConditionalPrevalence)}</td></tr>)}</tbody></table></Card></section>

    <section><h2 className="mb-3 font-display text-3xl text-slate">SSA baseline mortality curve</h2><Card className="overflow-x-auto"><table className="w-full min-w-[700px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Age</th><th className="px-5 py-3 text-right">Male mortality</th><th className="px-5 py-3 text-right">Female mortality</th></tr></thead><tbody>{mortalityCurve.map((row) => <tr key={row.age} className="border-t border-slate/10"><td className="nums px-5 py-3">{row.age}</td><td className="nums px-5 py-3 text-right">{row.M ? rate.format(row.M.MortalityRate) : "—"}</td><td className="nums px-5 py-3 text-right">{row.F ? rate.format(row.F.MortalityRate) : "—"}</td></tr>)}</tbody></table></Card></section>

    <section><h2 className="mb-3 font-display text-3xl text-slate">Wellness participation</h2><p className="mb-3 text-sm text-muted">This annual rollup queries vWellnessActivityEnrollmentYear with NOEXPAND, using the materialized annual grain from the physical design.</p><Card className="overflow-x-auto"><table className="w-full min-w-[700px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Activity year</th><th className="px-5 py-3 text-right">Participants</th><th className="px-5 py-3 text-right">Qualifying activities</th><th className="px-5 py-3 text-right">Enrollment coverage</th></tr></thead><tbody>{data.wellness.map((row) => <tr key={row.ActivityYear} className="border-t border-slate/10"><td className="nums px-5 py-3">{row.ActivityYear}</td><td className="nums px-5 py-3 text-right">{number.format(row.ParticipatingEnrollments)}</td><td className="nums px-5 py-3 text-right">{number.format(row.QualifyingActivities)}</td><td className="nums px-5 py-3 text-right">{percent.format(Number(row.ParticipatingEnrollments) / Number(row.TotalEnrollments))}</td></tr>)}</tbody></table></Card></section>

    <section><h2 className="mb-3 font-display text-3xl text-slate">Refresh job history</h2><Card className="overflow-x-auto"><table className="w-full min-w-[850px] border-collapse text-left text-sm"><thead className="bg-paper text-xs uppercase tracking-[0.1em] text-muted"><tr><th className="px-5 py-3">Run</th><th className="px-5 py-3">Started</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Version</th><th className="px-5 py-3">Recorded parameters</th></tr></thead><tbody>{data.runs.map((run) => <tr key={run.RunID} className="border-t border-slate/10"><td className="nums px-5 py-4">#{run.RunID}</td><td className="nums px-5 py-4">{run.StartedAt}</td><td className="px-5 py-4">{run.Status}</td><td className="nums px-5 py-4">{run.NewRateVersionID ? `v${run.NewRateVersionID}` : "—"}</td><td className="max-w-md px-5 py-4 text-xs leading-5 text-muted">{run.Notes ?? "No notes"}</td></tr>)}</tbody></table></Card></section>
  </div>;
}
