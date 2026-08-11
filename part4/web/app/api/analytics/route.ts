// Jingrui Feng (jf4446) - analytics data endpoint
import { NextResponse } from "next/server";
import { getPool } from "@/lib/db";
import {
  ANALYTICS_BRFSS_PREVALENCE,
  ANALYTICS_SSA_MORTALITY,
  ANALYTICS_WELLNESS_PARTICIPATION,
  RATE_VERSION_HISTORY,
  REFRESH_RUN_HISTORY,
} from "@/lib/queries";
import type {
  BRFSSPrevalenceRow, RateVersionRow, RefreshRunRow, SSAMortalityRow, WellnessParticipationRow,
} from "@/lib/types";

export async function GET() {
  try {
    const pool = await getPool();
    const [versions, prevalence, mortality, wellness, runs] = await Promise.all([
      pool.request().query<RateVersionRow>(RATE_VERSION_HISTORY),
      pool.request().query<BRFSSPrevalenceRow>(ANALYTICS_BRFSS_PREVALENCE),
      pool.request().query<SSAMortalityRow>(ANALYTICS_SSA_MORTALITY),
      pool.request().query<WellnessParticipationRow>(ANALYTICS_WELLNESS_PARTICIPATION),
      pool.request().query<RefreshRunRow>(REFRESH_RUN_HISTORY),
    ]);
    return NextResponse.json({
      versions: versions.recordset, prevalence: prevalence.recordset, mortality: mortality.recordset,
      wellness: wellness.recordset, runs: runs.recordset,
    });
  } catch {
    return NextResponse.json({ message: "Analytics are unavailable. Check the Azure SQL connection and try again." }, { status: 500 });
  }
}
