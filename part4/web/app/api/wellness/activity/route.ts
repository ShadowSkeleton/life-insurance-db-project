// Jingrui Feng (jf4446) - wellness activity endpoint
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(request: Request) {
  try {
    const { enrollmentId, activityType } = await request.json();
    if (!Number.isInteger(Number(enrollmentId)) || !["Gym Visit", "Step Challenge", "Health Screen", "Nutrition Log"].includes(activityType)) {
      return NextResponse.json({ message: "Select a valid enrollment and activity type." }, { status: 400 });
    }
    const inserted = await prisma.wellnessActivity.create({
      data: {
        EnrollmentID: Number(enrollmentId),
        ActivityDate: new Date(),
        ActivityType: activityType,
        VerifiedFlag: "Y",
      },
      select: { ActivityID: true },
    });
    return NextResponse.json({ activityId: inserted.ActivityID });
  } catch {
    return NextResponse.json({ message: "The activity could not be recorded. No activity was added." }, { status: 500 });
  }
}
