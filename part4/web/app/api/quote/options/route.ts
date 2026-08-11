// Jingrui Feng (jf4446) - product options endpoint
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    const products = await prisma.product.findMany({
      select: { ProductID: true, LineOfBusiness: true, SeriesName: true, PlanName: true, Description: true },
      orderBy: { ProductID: "asc" },
    });
    return NextResponse.json({ products });
  } catch {
    return NextResponse.json({ message: "Products are unavailable. Check the local database connection and try again." }, { status: 503 });
  }
}
