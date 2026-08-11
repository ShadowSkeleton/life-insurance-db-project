// Jingrui Feng (jf4446) - quote creation endpoint
import { NextResponse } from "next/server";
import { ageToAgeBand, bmiToBMIBand } from "@/lib/bands";
import { getPool, sql } from "@/lib/db";
import { premiumFromBaseRate } from "@/lib/pricing";
import { CUSTOMER_EXISTS, INSERT_APPLICATION, PRIOR_QUOTE_FOR_PROFILE, QUOTE_ACTIVE_RATE } from "@/lib/queries";
import type { BMIBand, DiabetesStatus, Gender, PriorQuoteRow, QuoteRateRow, SmokingStatus } from "@/lib/types";

const faceAmounts = new Set([100000, 250000, 500000, 1000000]);

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const customerId = Number(body.customerId);
    const productId = Number(body.productId);
    const age = Number(body.age);
    const bmi = Number(body.bmi);
    const faceAmount = Number(body.faceAmount);
    const gender = body.gender as Gender;
    const smokingStatus = body.smokingStatus as SmokingStatus;
    const diabetesStatus = body.diabetesStatus as DiabetesStatus;
    if (!Number.isInteger(customerId) || !Number.isInteger(productId) || !Number.isInteger(age) || !Number.isFinite(bmi)
      || !faceAmounts.has(faceAmount) || !["F", "M"].includes(gender)
      || !["never", "former", "current"].includes(smokingStatus) || !["yes", "no"].includes(diabetesStatus)) {
      return NextResponse.json({ message: "Enter a complete profile and one of the approved face amounts." }, { status: 400 });
    }
    const ageBand = ageToAgeBand(age);
    const bmiBand: BMIBand = bmiToBMIBand(bmi);
    const pool = await getPool();
    const customer = await pool.request().input("customerId", sql.Int, customerId).query(CUSTOMER_EXISTS);
    if (!customer.recordset[0]) {
      return NextResponse.json({ message: "The selected customer does not exist. Use an existing Customer ID." }, { status: 400 });
    }
    const rate = await pool.request()
      .input("productId", sql.Int, productId).input("ageBand", sql.VarChar(10), ageBand)
      .input("gender", sql.VarChar(1), gender).input("smokingStatus", sql.VarChar(10), smokingStatus)
      .input("diabetesStatus", sql.VarChar(10), diabetesStatus).input("bmiBand", sql.VarChar(10), bmiBand)
      .query<QuoteRateRow>(QUOTE_ACTIVE_RATE);
    const row = rate.recordset[0];
    if (!row) {
      return NextResponse.json({ message: "No current rate matches this profile. Route this case for review." }, { status: 404 });
    }
    const premium = premiumFromBaseRate(Number(row.BaseRate), faceAmount);
    const prior = await pool.request()
      .input("productId", sql.Int, productId).input("age", sql.Int, age).input("gender", sql.VarChar(1), gender)
      .input("smokingStatus", sql.VarChar(10), smokingStatus).input("diabetesStatus", sql.VarChar(10), diabetesStatus)
      .input("bmi", sql.Decimal(5, 2), bmi).input("faceAmount", sql.Decimal(12, 2), faceAmount)
      .input("rateVersionId", sql.Int, row.RateVersionID).query<PriorQuoteRow>(PRIOR_QUOTE_FOR_PROFILE);
    const inserted = await pool.request()
      .input("customerId", sql.Int, customerId).input("productId", sql.Int, productId)
      .input("age", sql.Int, age).input("gender", sql.VarChar(1), gender)
      .input("smokingStatus", sql.VarChar(10), smokingStatus).input("diabetesStatus", sql.VarChar(10), diabetesStatus)
      .input("bmi", sql.Decimal(5, 2), bmi).input("ageBand", sql.VarChar(10), ageBand)
      .input("bmiBand", sql.VarChar(10), bmiBand).input("faceAmount", sql.Decimal(12, 2), faceAmount)
      .input("rateVersionId", sql.Int, row.RateVersionID).input("premium", sql.Decimal(12, 2), premium)
      .query<{ ApplicationID: number }>(INSERT_APPLICATION);
    return NextResponse.json({
      applicationId: inserted.recordset[0].ApplicationID, premium, ageBand, bmiBand,
      rateVersionId: row.RateVersionID, baseRate: Number(row.BaseRate), mortalityMultiplier: Number(row.MortalityMultiplier),
      priorQuote: prior.recordset[0] ?? null,
    });
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("Age must")) {
      return NextResponse.json({ message: error.message }, { status: 400 });
    }
    return NextResponse.json({ message: "The quote could not be saved. Check the local database and try again." }, { status: 500 });
  }
}
