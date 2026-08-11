// Jingrui Feng (jf4446) - biometric screening endpoint
import { NextResponse } from "next/server";
import { getPool, sql } from "@/lib/db";
import { INSERT_RISK_IMPROVEMENT, WELLNESS_ENROLLMENT_CONTEXT } from "@/lib/queries";

const measureTypes = new Set(["BMI", "smoking", "exercise"]);

export async function POST(request: Request) {
  try {
    const { enrollmentId, measureDate, measureType, baselineValue, measureValue } = await request.json();
    const enrollment = Number(enrollmentId);
    const baseline = Number(baselineValue);
    const current = Number(measureValue);
    if (!Number.isInteger(enrollment) || !measureTypes.has(measureType) || !Number.isFinite(baseline) || baseline <= 0 || !Number.isFinite(current) || current < 0) {
      return NextResponse.json({ message: "Enter an enrollment, supported measurement type, positive baseline, and current value." }, { status: 400 });
    }
    const pool = await getPool();
    const context = await pool.request().input("enrollmentId", sql.Int, enrollment)
      .query<{ EnrollDate: string; RenewalDate: string }>(WELLNESS_ENROLLMENT_CONTEXT);
    const enrollmentContext = context.recordset[0];
    if (!enrollmentContext) {
      return NextResponse.json({ message: "The wellness enrollment does not exist." }, { status: 404 });
    }
    const { EnrollDate: enrollDate, RenewalDate: renewalDate } = enrollmentContext;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(measureDate) || measureDate < enrollDate || measureDate >= renewalDate) {
      return NextResponse.json({ message: `The screening date must be on or after enrollment (${enrollDate}) and before projected renewal (${renewalDate}).` }, { status: 400 });
    }
    const rawPct = measureType === "exercise" ? ((current - baseline) / baseline) * 100 : ((baseline - current) / baseline) * 100;
    const improvementPct = Math.round(rawPct * 100) / 100;
    const inserted = await pool.request().input("enrollmentId", sql.Int, enrollment)
      .input("measureDate", sql.Date, measureDate).input("measureType", sql.VarChar(20), measureType)
      .input("measureValue", sql.Decimal(8, 2), current).input("baselineValue", sql.Decimal(8, 2), baseline)
      .input("improvementPct", sql.Decimal(5, 2), improvementPct).query<{ ImprovementID: number }>(INSERT_RISK_IMPROVEMENT);
    return NextResponse.json({ improvementId: inserted.recordset[0].ImprovementID, improvementPct, renewalDate });
  } catch {
    return NextResponse.json({ message: "The biometric screening could not be recorded. No improvement was added." }, { status: 500 });
  }
}
