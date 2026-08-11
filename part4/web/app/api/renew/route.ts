// Part 4 renewal endpoint: preserves Contract as the issue-time record.
import { NextResponse } from "next/server";
import { getPool, sql } from "@/lib/db";
import { premiumFromBaseRate, renewalPremium } from "@/lib/pricing";
import {
  ACTIVE_PROFILE_RATE,
  ACTIVE_RATE_VERSION,
  INSERT_POLICY_RENEWAL,
  POLICY_RENEWAL_EXISTS_FOR_UPDATE,
  RENEWAL_POLICY,
  WELLNESS_CREDIT,
} from "@/lib/queries";

type RenewalPolicy = {
  ContractID: number;
  ApplicationID: number | null;
  ProductID: number | null;
  FaceAmount: number | null;
  AgeBand: string | null;
  Gender: string | null;
  SmokingStatus: string | null;
  DiabetesStatus: string | null;
  BMIBand: string | null;
  EnrollmentID: number | null;
};

type InsertedRenewal = {
  RenewalID: number;
  ContractID: number;
  NewRateVersionID: number;
  WellnessDiscountPct: number | null;
  FinalPremium: number | null;
};

class RenewalRequestError extends Error {}

function validDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
}

export async function POST(request: Request) {
  let transaction: sql.Transaction | undefined;
  let begun = false;
  try {
    const body: unknown = await request.json();
    const contractId = typeof body === "object" && body !== null ? Number((body as { ContractID?: unknown; contractId?: unknown }).ContractID ?? (body as { contractId?: unknown }).contractId) : NaN;
    const renewalDate = typeof body === "object" && body !== null ? ((body as { RenewalDate?: unknown; renewalDate?: unknown }).RenewalDate ?? (body as { renewalDate?: unknown }).renewalDate) : undefined;
    if (!Number.isInteger(contractId) || contractId < 1) throw new RenewalRequestError("ContractID must be a positive integer.");
    if (!validDate(renewalDate)) throw new RenewalRequestError("RenewalDate must be a valid YYYY-MM-DD date.");

    const pool = await getPool();
    transaction = new sql.Transaction(pool);
    await transaction.begin(sql.ISOLATION_LEVEL.READ_COMMITTED);
    begun = true;

    const policy = (await transaction.request().input("contractId", sql.Int, contractId).query<RenewalPolicy>(RENEWAL_POLICY)).recordset[0];
    if (!policy) throw new RenewalRequestError("Contract not found.");
    if (policy.ApplicationID === null) throw new RenewalRequestError("This contract has no APPLICATION, so it cannot be renewed.");

    const duplicate = await transaction.request().input("contractId", sql.Int, contractId)
      .input("renewalDate", sql.Date, renewalDate).query(POLICY_RENEWAL_EXISTS_FOR_UPDATE);
    if (duplicate.recordset[0]) throw new RenewalRequestError("A renewal already exists for this contract and renewal date.");

    const activeVersion = (await transaction.request().query<{ RateVersionID: number }>(ACTIVE_RATE_VERSION)).recordset[0];
    if (!activeVersion) throw new RenewalRequestError("No active RATE_VERSION exists.");
    if ([policy.ProductID, policy.FaceAmount, policy.AgeBand, policy.Gender, policy.SmokingStatus, policy.DiabetesStatus, policy.BMIBand].some((value) => value === null)) {
      throw new RenewalRequestError("No RATE matches this contract profile under the active rate version.");
    }

    const activeRate = await transaction.request()
      .input("productId", sql.Int, policy.ProductID!)
      .input("ageBand", sql.VarChar(10), policy.AgeBand!)
      .input("gender", sql.VarChar(1), policy.Gender!)
      .input("smokingStatus", sql.VarChar(10), policy.SmokingStatus!)
      .input("diabetesStatus", sql.VarChar(10), policy.DiabetesStatus!)
      .input("bmiBand", sql.VarChar(10), policy.BMIBand!)
      .query<{ ActiveRateVersionID: number; BaseRate: number }>(ACTIVE_PROFILE_RATE);
    const rate = activeRate.recordset[0];
    if (!rate) throw new RenewalRequestError("No RATE matches this contract profile under the active rate version.");

    const credit = policy.EnrollmentID === null ? 0 : Number((await transaction.request()
      .input("enrollmentId", sql.Int, policy.EnrollmentID)
      .input("renewalDate", sql.Date, renewalDate)
      .query<{ WellnessDiscountPct: number }>(WELLNESS_CREDIT)).recordset[0]?.WellnessDiscountPct ?? 0);
    const baseRenewalPremium = premiumFromBaseRate(Number(rate.BaseRate), Number(policy.FaceAmount));
    const finalPremium = renewalPremium(baseRenewalPremium, credit);

    const inserted = (await transaction.request()
      .input("contractId", sql.Int, contractId)
      .input("renewalDate", sql.Date, renewalDate)
      .input("newRateVersionId", sql.Int, rate.ActiveRateVersionID)
      .input("wellnessDiscountPct", sql.Decimal(5, 2), credit)
      .input("finalPremium", sql.Decimal(12, 2), finalPremium)
      .query<InsertedRenewal>(INSERT_POLICY_RENEWAL)).recordset[0];

    await transaction.commit();
    begun = false;
    return NextResponse.json({
      renewal: { ...inserted, RenewalDate: renewalDate },
      currentRatePremium: baseRenewalPremium,
      wellnessDiscountPct: credit,
      finalRenewalPremium: finalPremium,
      message: "Renewal recorded. Contract.ModalPremium and Contract.IssuedRateVersionID were not changed.",
    }, { status: 201 });
  } catch (error) {
    if (begun && transaction) {
      try { await transaction.rollback(); } catch { /* Preserve the original response. */ }
    }
    if (error instanceof RenewalRequestError) return NextResponse.json({ message: error.message }, { status: 400 });
    return NextResponse.json({ message: "Renewal could not be recorded. Check the local database and try again." }, { status: 500 });
  }
}
