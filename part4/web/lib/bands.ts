// Jingrui Feng (jf4446) - applicant profile banding
import type { BMIBand } from "@/lib/types";

// Source of truth: BRFSS _AGEG5YR handling in build_training_frame.py.
// Quotes must use these same labels to join a profile to RISK_FACTOR.
export function ageToAgeBand(age: number): string {
  if (age >= 18 && age <= 24) return "18-24";
  if (age <= 29) return "25-29";
  if (age <= 34) return "30-34";
  if (age <= 39) return "35-39";
  if (age <= 44) return "40-44";
  if (age <= 49) return "45-49";
  if (age <= 54) return "50-54";
  if (age <= 59) return "55-59";
  if (age <= 64) return "60-64";
  if (age <= 69) return "65-69";
  if (age <= 74) return "70-74";
  if (age <= 79) return "75-79";
  if (age <= 99) return "80-99";
  throw new Error("Age must be between 18 and 99 for the available BRFSS rate bands.");
}

// Source: BRFSS _BMI5CAT, using CDC and WHO category cut points. The staged
// STG_BRFSS_RECORD data was verified as 12.53–18.49, 18.50–24.99,
// 25.00–29.99, and 30.00–99.79 for the four bands respectively.
export function bmiToBMIBand(bmi: number): BMIBand {
  if (bmi < 18.5) return "under";
  if (bmi < 25.0) return "normal";
  if (bmi < 30.0) return "over";
  return "obese";
}
