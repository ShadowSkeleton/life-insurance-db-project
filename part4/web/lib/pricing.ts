// Jingrui Feng (jf4446) - premium calculation helpers
export function premiumFromBaseRate(baseRate: number, faceAmount: number): number {
  return Math.round(baseRate * faceAmount) / 1000;
}

export function renewalPremium(basePremium: number, creditPct: number): number {
  return Math.round(basePremium * (1 - creditPct / 100) * 100) / 100;
}

export const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

export const number = new Intl.NumberFormat("en-US");
