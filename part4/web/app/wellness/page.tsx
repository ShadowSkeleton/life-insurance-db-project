// Jingrui Feng (jf4446) - wellness participation page
"use client";

import { FormEvent, useEffect, useState } from "react";
import { Activity, Calculator, CirclePlus, ClipboardPlus, Pin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { money, number } from "@/lib/pricing";
import type { PolicyRenewalRow, WellnessCandidate, WellnessDetail, WellnessProgramRow } from "@/lib/types";

type WellnessResponse = {
  candidates: WellnessCandidate[];
  programs: WellnessProgramRow[];
  policy: WellnessDetail;
  baseRenewalPremium: number;
  projectedRenewalPremium: number;
  existingRenewal: PolicyRenewalRow | null;
  message?: string;
};

const inputClass = "mt-2 block w-full border border-slate/20 bg-white px-3 py-2 outline-none focus:border-active focus:ring-2 focus:ring-active/20";
const today = new Date().toISOString().slice(0, 10);

export default function WellnessPage() {
  const [data, setData] = useState<WellnessResponse | null>(null);
  const [selected, setSelected] = useState("");
  const [manualContract, setManualContract] = useState("");
  const [activityType, setActivityType] = useState("Gym Visit");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [renewing, setRenewing] = useState(false);
  const [message, setMessage] = useState("");
  const [enrollment, setEnrollment] = useState({ programId: "", enrollDate: today });
  const [screening, setScreening] = useState({ measureType: "BMI", baselineValue: "30", measureValue: "25.5", measureDate: today });

  async function load(contractId?: string, clearMessage = true) {
    setLoading(true);
    if (clearMessage) setMessage("");
    try {
      const normalizedContractId = contractId?.trim().replace(/^#/, "");
      const response = await fetch(`/api/wellness${normalizedContractId ? `?contractId=${encodeURIComponent(normalizedContractId)}` : ""}`);
      const next = await response.json();
      if (!response.ok) throw new Error(next.message);
      setData(next);
      setSelected(String(next.policy.ContractID));
      setEnrollment((current) => ({ ...current, programId: current.programId || String(next.programs[0]?.WellnessProgramID ?? "") }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Wellness details could not be read.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function enrollPolicy(event: FormEvent) {
    event.preventDefault();
    if (!data) return;
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch("/api/wellness/enrollment", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contractId: data.policy.ContractID, wellnessProgramId: Number(enrollment.programId), enrollDate: enrollment.enrollDate }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message);
      setMessage(`Wellness enrollment #${result.enrollmentId} recorded. Activity and screening can now be recorded before ${result.renewalDate}.`);
      await load(selected, false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The wellness enrollment could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function addActivity(event: FormEvent) {
    event.preventDefault();
    if (!data?.policy.EnrollmentID) return;
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch("/api/wellness/activity", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enrollmentId: data.policy.EnrollmentID, activityType }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message);
      setMessage(`Verified activity #${result.activityId} recorded. The yearly indexed-view total has refreshed; the credit is unchanged.`);
      await load(selected, false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The activity could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function recordScreening(event: FormEvent) {
    event.preventDefault();
    if (!data?.policy.EnrollmentID) return;
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch("/api/wellness/screening", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enrollmentId: data.policy.EnrollmentID, ...screening }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message);
      setMessage(`Biometric screening #${result.improvementId} recorded with ${Number(result.improvementPct).toFixed(2)}% measured improvement. The renewal credit has refreshed.`);
      await load(selected, false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The screening could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function renewPolicy() {
    if (!data) return;
    setRenewing(true);
    setMessage("");
    try {
      const response = await fetch("/api/renew", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ContractID: data.policy.ContractID, RenewalDate: data.policy.RenewalDate }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message);
      setMessage(`Renewal #${result.renewal.RenewalID} was recorded. The Contract issue-time premium and issued rate version remain unchanged.`);
      await load(selected, false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The renewal could not be recorded.");
    } finally {
      setRenewing(false);
    }
  }

  const policy = data?.policy;
  return <div className="space-y-7">
    <div className="border-b border-slate/15 pb-7">
      <p className="font-mono text-xs font-semibold tracking-[0.16em] text-active">UC-3 · UC-5</p>
      <h1 className="mt-2 font-display text-4xl text-slate md:text-5xl">Wellness and renewal</h1>
      <p className="mt-3 max-w-2xl text-muted">Verified annual activity comes from the materialized yearly view. A dated measured improvement supplies the capped renewal credit.</p>
    </div>

    {loading ? <Card className="p-6 text-muted">Loading a policy…</Card> : policy && data ? <>
      <Card className="grid gap-4 p-5 md:grid-cols-[1fr_260px]">
        <label className="text-sm font-semibold text-ink">Wellness-linked policy
          <select className={inputClass} value={selected} onChange={(event) => void load(event.target.value)}>
            {data.candidates.map((item) => <option key={item.ContractID} value={item.ContractID}>#{item.ContractID} · {item.ContractNumber}</option>)}
          </select>
        </label>
        <form className="self-end" onSubmit={(event) => { event.preventDefault(); if (manualContract) void load(manualContract); }}>
          <label className="text-sm font-semibold text-ink">Check a bound policy
            <input className={inputClass} min="1" placeholder="Contract ID" value={manualContract} onChange={(event) => setManualContract(event.target.value)} />
          </label>
          <Button type="submit" variant="secondary" className="mt-2">Open policy</Button>
        </form>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <Card className="p-6">
            <p className="font-mono text-xs font-semibold tracking-[0.16em] text-active">POLICY LEDGER</p>
            <h2 className="mt-2 font-display text-3xl text-slate">{policy.ContractNumber}</h2>
            <dl className="mt-6 grid grid-cols-2 gap-5 text-sm">
              <div><dt className="text-muted">Issued premium</dt><dd className="nums mt-1 font-semibold">{policy.ModalPremium === null ? "Not recorded" : money.format(policy.ModalPremium)}</dd></div>
              <div><dt className="text-muted">Issued version</dt><dd className="nums mt-1 flex items-center gap-1 font-semibold"><Pin size={14} className="text-old" />v{policy.IssuedRateVersionID}</dd></div>
              <div><dt className="text-muted">Enrollment</dt><dd className="nums mt-1 font-semibold">{policy.EnrollmentID ? `#${policy.EnrollmentID}` : "Not enrolled"}</dd></div>
              <div><dt className="text-muted">Current book</dt><dd className="nums mt-1 font-semibold text-active">v{policy.ActiveRateVersionID}</dd></div>
            </dl>
          </Card>

          {!policy.EnrollmentID && <Card className="p-6">
            <div className="flex items-start gap-3"><CirclePlus size={22} className="mt-1 text-active" /><div><p className="font-mono text-xs font-semibold tracking-[0.15em] text-active">UC-3 ENROLLMENT</p><h2 className="mt-1 font-display text-2xl text-slate">Enrol in wellness program</h2></div></div>
            <form onSubmit={enrollPolicy} className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">Wellness program
                <select className={inputClass} value={enrollment.programId} onChange={(event) => setEnrollment((value) => ({ ...value, programId: event.target.value }))}>
                  {data.programs.map((program) => <option key={program.WellnessProgramID} value={program.WellnessProgramID}>{program.ProgramName}{program.PartnerGym ? ` · ${program.PartnerGym}` : ""}</option>)}
                </select>
              </label>
              <label className="text-sm font-semibold">Enrollment date
                <input className={inputClass} type="date" value={enrollment.enrollDate} onChange={(event) => setEnrollment((value) => ({ ...value, enrollDate: event.target.value }))} />
              </label>
              <div className="sm:col-span-2"><Button type="submit" disabled={saving}>{saving ? "Enrolling…" : "Enrol in wellness"}</Button></div>
            </form>
            <p className="mt-4 text-xs leading-5 text-muted">Enrollment must be before the projected renewal on {policy.RenewalDate}. The program is selected from the published wellness-program table. A screening can only follow this enrollment in the workflow.</p>
          </Card>}

          <Card className="p-6">
            <div className="flex items-start gap-3"><Activity size={22} className="mt-1 text-active" /><div><p className="font-mono text-xs font-semibold tracking-[0.15em] text-active">YEARLY ACTIVITY</p><p className="nums mt-2 text-4xl font-semibold text-slate">{number.format(policy.QualifyingActivityCount)}</p><p className="mt-1 text-sm text-muted">verified activities in {new Date().getFullYear()}</p></div></div>
            {policy.EnrollmentID ? <form onSubmit={addActivity} className="mt-6 flex flex-wrap gap-3"><select className="border border-slate/20 bg-white px-3 py-2 text-sm outline-none focus:border-active" value={activityType} onChange={(event) => setActivityType(event.target.value)}><option>Gym Visit</option><option>Step Challenge</option><option>Health Screen</option><option>Nutrition Log</option></select><Button type="submit" disabled={saving}>{saving ? "Recording…" : "Record activity"}</Button></form> : <p className="mt-5 border-l-2 border-old bg-paper p-3 text-sm text-muted">Enrol this policy first. Activity is participation evidence, not a renewal credit.</p>}
            <p className="mt-4 text-xs leading-5 text-muted">Participation alone does not alter the credit. A dated biometric measurement is required before a renewal offset is defensible.</p>
          </Card>

          {policy.EnrollmentID && <Card className="p-6">
            <div className="flex items-start gap-3"><ClipboardPlus size={22} className="mt-1 text-active" /><div><p className="font-mono text-xs font-semibold tracking-[0.15em] text-active">PERIODIC MEASUREMENT</p><h2 className="mt-1 font-display text-2xl text-slate">Record biometric screening</h2></div></div>
            <form onSubmit={recordScreening} className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">Measure type<select className={inputClass} value={screening.measureType} onChange={(event) => setScreening((value) => ({ ...value, measureType: event.target.value }))}><option value="BMI">BMI</option><option value="smoking">Smoking</option><option value="exercise">Exercise</option></select></label>
              <label className="text-sm font-semibold">Screening date<input className={inputClass} type="date" value={screening.measureDate} onChange={(event) => setScreening((value) => ({ ...value, measureDate: event.target.value }))} /></label>
              <label className="text-sm font-semibold">Baseline value<input className={inputClass} type="number" min="0.01" step="0.01" value={screening.baselineValue} onChange={(event) => setScreening((value) => ({ ...value, baselineValue: event.target.value }))} /></label>
              <label className="text-sm font-semibold">Current value<input className={inputClass} type="number" min="0" step="0.01" value={screening.measureValue} onChange={(event) => setScreening((value) => ({ ...value, measureValue: event.target.value }))} /></label>
              <div className="sm:col-span-2"><Button type="submit" disabled={saving}>{saving ? "Recording…" : "Record screening"}</Button></div>
            </form>
            <p className="mt-4 text-xs leading-5 text-muted">The screening date must be on or after enrollment and before projected renewal on {policy.RenewalDate}. `DATE` stores no time of day, so same-day enrollment and screening are permitted only after the enrollment action has been saved. BMI and smoking improvement are baseline minus current, divided by baseline; exercise uses current minus baseline.</p>
          </Card>}
        </div>

        <Card className="overflow-hidden">
          <div className="border-b border-slate/10 bg-slate p-6 text-white">
            <p className="font-mono text-xs tracking-[0.16em] text-[#A8E1E0]">{data.existingRenewal ? "RECORDED RENEWAL" : "PROJECTED RENEWAL"} · {policy.RenewalDate}</p>
            <p className="nums mt-4 text-5xl font-semibold">{money.format(data.existingRenewal?.FinalPremium ?? data.projectedRenewalPremium)}</p>
            <p className="mt-2 text-sm text-slate-200">Current active rate book, after eligible wellness credit</p>
          </div>
          <div className="p-6">
            <div className="flex items-center gap-2"><Calculator size={18} className="text-active" /><h2 className="font-display text-2xl text-slate">{data.existingRenewal ? "Written renewal" : "Visible arithmetic"}</h2></div>
            <div className="nums mt-6 space-y-3 text-sm">
              <div className="flex justify-between border-b border-slate/10 pb-3"><span className="text-muted">Current-rate premium before credit</span><span>{money.format(data.baseRenewalPremium)}</span></div>
              <div className="flex justify-between border-b border-slate/10 pb-3"><span className="text-muted">Measured wellness credit</span><span className="text-active">−{Number(data.existingRenewal?.WellnessDiscountPct ?? policy.WellnessDiscountPct).toFixed(2)}%</span></div>
              <div className="flex justify-between border-b border-slate/10 pb-3"><span className="text-muted">New rate version</span><span>v{data.existingRenewal?.NewRateVersionID ?? policy.ActiveRateVersionID}</span></div>
              {data.existingRenewal && <div className="flex justify-between border-b border-slate/10 pb-3"><span className="text-muted">POLICY_RENEWAL row</span><span>#{data.existingRenewal.RenewalID}</span></div>}
              <div className="flex justify-between pt-2 text-lg font-semibold"><span>{data.existingRenewal ? "Final renewal premium" : "Projected renewal premium"}</span><span>{money.format(data.existingRenewal?.FinalPremium ?? data.projectedRenewalPremium)}</span></div>
            </div>
            {data.existingRenewal ? <p className="mt-6 border-l-2 border-active bg-paper p-3 text-sm leading-6 text-muted">This is the saved POLICY_RENEWAL record. Contract.ModalPremium and Contract.IssuedRateVersionID remain the original issue-time values.</p> : <><Button className="mt-6 w-full" onClick={() => void renewPolicy()} disabled={renewing}>{renewing ? "Recording renewal…" : "Record renewal"}</Button><p className="mt-4 text-sm leading-6 text-muted">This action writes one POLICY_RENEWAL row. The Contract row remains unchanged, preserving the issued premium and rate version.</p></>}
          </div>
        </Card>
      </div>
    </> : <Card className="p-6 text-ink">{message || "No wellness-linked policy is available."}</Card>}
    {message && policy && <p className="border-l-4 border-active bg-white p-3 text-sm text-ink" aria-live="polite">{message}</p>}
  </div>;
}
