// Jingrui Feng (jf4446) - policy bind endpoint
import { NextResponse } from "next/server";
import { getPool, sql } from "@/lib/db";
import { APPLICATION_FOR_BIND, INSERT_BOUND_CONTRACT, MARK_APPLICATION_BOUND, NEXT_CONTRACT_ID } from "@/lib/queries";

export async function POST(request: Request) {
  try {
    const applicationId = Number((await request.json()).applicationId);
    if (!Number.isInteger(applicationId)) return NextResponse.json({ message: "A valid quoted application is required." }, { status: 400 });
    const pool = await getPool();
    const transaction = new sql.Transaction(pool);
    await transaction.begin(sql.ISOLATION_LEVEL.SERIALIZABLE);
    try {
      const application = await new sql.Request(transaction).input("applicationId", sql.Int, applicationId).query<{
        ApplicationID: number; ProductID: number; QuotedRateVersionID: number; QuotedPremium: number;
      }>(APPLICATION_FOR_BIND);
      const quote = application.recordset[0];
      if (!quote) throw new Error("not-quoted");
      const next = await new sql.Request(transaction).query<{ ContractID: number }>(NEXT_CONTRACT_ID);
      const contractId = next.recordset[0].ContractID;
      await new sql.Request(transaction)
        .input("contractNumber", sql.VarChar(20), `DEMO-${contractId}`)
        .input("premium", sql.Decimal(12, 2), quote.QuotedPremium)
        .input("contractId", sql.Int, contractId).input("productId", sql.Int, quote.ProductID)
        .input("rateVersionId", sql.Int, quote.QuotedRateVersionID).input("applicationId", sql.Int, applicationId)
        .query(INSERT_BOUND_CONTRACT);
      await new sql.Request(transaction).input("applicationId", sql.Int, applicationId).query(MARK_APPLICATION_BOUND);
      await transaction.commit();
      return NextResponse.json({ contractId, rateVersionId: quote.QuotedRateVersionID });
    } catch (error) {
      await transaction.rollback();
      if (error instanceof Error && error.message === "not-quoted") {
        return NextResponse.json({ message: "This quote is no longer available to bind." }, { status: 409 });
      }
      throw error;
    }
  } catch {
    return NextResponse.json({ message: "The policy could not be bound. No policy was created." }, { status: 500 });
  }
}
