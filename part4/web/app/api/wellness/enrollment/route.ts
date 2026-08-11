// Jingrui Feng (jf4446) - wellness enrollment endpoint
import { NextResponse } from "next/server";
import { getPool, sql } from "@/lib/db";
import {
  ENROLLMENT_EXISTS_FOR_CONTRACT,
  INSERT_WELLNESS_ENROLLMENT,
  NEXT_PROJECTED_RENEWAL_DATE,
  WELLNESS_PROGRAM_EXISTS,
} from "@/lib/queries";

export async function POST(request: Request) {
  try {
    const { contractId, wellnessProgramId, enrollDate } = await request.json();
    const contract = Number(contractId);
    const program = Number(wellnessProgramId);
    if (!Number.isInteger(contract) || !Number.isInteger(program) || !/^\d{4}-\d{2}-\d{2}$/.test(enrollDate)) {
      return NextResponse.json({ message: "Select a contract, program, and valid enrollment date." }, { status: 400 });
    }
    const pool = await getPool();
    const existing = await pool.request().input("contractId", sql.Int, contract).query(ENROLLMENT_EXISTS_FOR_CONTRACT);
    if (existing.recordset[0]) {
      return NextResponse.json({ message: "This policy already has a wellness enrollment." }, { status: 409 });
    }
    const validProgram = await pool.request().input("wellnessProgramId", sql.Int, program).query(WELLNESS_PROGRAM_EXISTS);
    if (!validProgram.recordset[0]) {
      return NextResponse.json({ message: "Select a wellness program from the published program list." }, { status: 400 });
    }
    const renewal = await pool.request().query<{ RenewalDate: string }>(NEXT_PROJECTED_RENEWAL_DATE);
    const renewalDate = renewal.recordset[0].RenewalDate;
    if (enrollDate >= renewalDate) {
      return NextResponse.json({ message: `Enrollment must occur before the projected renewal date, ${renewalDate}.` }, { status: 400 });
    }
    const inserted = await pool.request().input("contractId", sql.Int, contract)
      .input("wellnessProgramId", sql.Int, program).input("enrollDate", sql.Date, enrollDate)
      .query<{ EnrollmentID: number }>(INSERT_WELLNESS_ENROLLMENT);
    return NextResponse.json({ enrollmentId: inserted.recordset[0].EnrollmentID, renewalDate });
  } catch {
    return NextResponse.json({ message: "The wellness enrollment could not be recorded. No enrollment was added." }, { status: 500 });
  }
}
