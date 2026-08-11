// Jingrui Feng (jf4446) - rate history endpoint
import { NextResponse } from "next/server";
import { getPool } from "@/lib/db";
import { DATA_SOURCE_STATE_HISTORY, RATE_VERSION_HISTORY, REFRESH_RUN_HISTORY } from "@/lib/queries";
import type { DataSourceStateRow, RateVersionRow, RefreshRunRow } from "@/lib/types";

export async function GET() {
  try {
    const pool = await getPool();
    // Keep these read requests separate.  The local SQL Server driver has a
    // pooled connection shared across hot reloads; serial reads keep the
    // demonstrator's audit ledger reliable without changing either query.
    const versions = await pool.request().query<RateVersionRow>(RATE_VERSION_HISTORY);
    const runs = await pool.request().query<RefreshRunRow>(REFRESH_RUN_HISTORY);
    const sourceStates = await pool.request().query<DataSourceStateRow>(DATA_SOURCE_STATE_HISTORY);
    return NextResponse.json({ versions: versions.recordset, runs: runs.recordset, sourceStates: sourceStates.recordset });
  } catch {
    return NextResponse.json({ message: "Rate-version history is unavailable. Check the local database and try again." }, { status: 500 });
  }
}
