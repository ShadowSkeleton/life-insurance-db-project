// Jingrui Feng (jf4446) - wellness policy endpoint
import { NextResponse } from "next/server";
import { getPool, sql } from "@/lib/db";
import { premiumFromBaseRate, renewalPremium } from "@/lib/pricing";
import { ACTIVE_PROFILE_RATE, POLICY_RENEWAL_FOR_CONTRACT_DATE, WELLNESS_CONTRACTS, WELLNESS_CREDIT, WELLNESS_POLICY, WELLNESS_PROGRAM_OPTIONS, WELLNESS_YEAR_ACTIVITY } from "@/lib/queries";
import type { PolicyRenewalRow, WellnessCandidate, WellnessDetail, WellnessProgramRow } from "@/lib/types";

export async function GET(request: Request) {
  try {
    const pool = await getPool();
    const candidates = await pool.request().query<WellnessCandidate>(WELLNESS_CONTRACTS);
    const programs = await pool.request().query<WellnessProgramRow>(WELLNESS_PROGRAM_OPTIONS);
    const requested = Number(new URL(request.url).searchParams.get("contractId"));
    const contractId = Number.isInteger(requested) && requested > 0 ? requested : candidates.recordset[0]?.ContractID;
    if (!contractId) return NextResponse.json({ message: "No wellness-linked policies are available." }, { status: 404 });
    const policy = await pool.request().input("contractId", sql.Int, contractId).query<WellnessDetail>(WELLNESS_POLICY);
    const row = policy.recordset[0];
    if (!row) return NextResponse.json({ message: "That policy is not linked to an application and wellness enrollment." }, { status: 404 });
    const rate = await pool.request()
      .input("productId", sql.Int, row.ProductID).input("ageBand", sql.VarChar(10), row.AgeBand)
      .input("gender", sql.VarChar(1), row.Gender).input("smokingStatus", sql.VarChar(10), row.SmokingStatus)
      .input("diabetesStatus", sql.VarChar(10), row.DiabetesStatus).input("bmiBand", sql.VarChar(10), row.BMIBand)
      .query<{ ActiveRateVersionID: number; BaseRate: number }>(ACTIVE_PROFILE_RATE);
    const active = rate.recordset[0];
    if (!active) return NextResponse.json({ message: "No active rate matches this policy profile." }, { status: 404 });
    const now = new Date();
    const renewalDate = new Date(now.getFullYear() + 1, now.getMonth(), now.getDate()).toISOString().slice(0, 10);
    const activity = row.EnrollmentID === null ? 0 : Number((await pool.request().input("enrollmentId", sql.Int, row.EnrollmentID)
      .input("activityYear", sql.Int, now.getFullYear()).query<{ QualifyingActivityCount: number }>(WELLNESS_YEAR_ACTIVITY)).recordset[0]?.QualifyingActivityCount ?? 0);
    const credit = row.EnrollmentID === null ? 0 : Number((await pool.request().input("enrollmentId", sql.Int, row.EnrollmentID)
      .input("renewalDate", sql.Date, renewalDate).query<{ WellnessDiscountPct: number }>(WELLNESS_CREDIT)).recordset[0]?.WellnessDiscountPct ?? 0);
    const baseRenewalPremium = premiumFromBaseRate(Number(active.BaseRate), Number(row.FaceAmount));
    const existingRenewal = (await pool.request().input("contractId", sql.Int, contractId)
      .input("renewalDate", sql.Date, renewalDate)
      .query<PolicyRenewalRow>(POLICY_RENEWAL_FOR_CONTRACT_DATE)).recordset[0] ?? null;
    return NextResponse.json({
      candidates: candidates.recordset, programs: programs.recordset,
      policy: { ...row, ...active, QualifyingActivityCount: activity, WellnessDiscountPct: credit, RenewalDate: renewalDate },
      baseRenewalPremium, projectedRenewalPremium: renewalPremium(baseRenewalPremium, credit), existingRenewal,
    });
  } catch {
    return NextResponse.json({ message: "Wellness information is unavailable. Check the local database and try again." }, { status: 500 });
  }
}
