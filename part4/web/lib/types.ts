// Jingrui Feng (jf4446) - application data types
export type Gender = "F" | "M";
export type SmokingStatus = "never" | "former" | "current";
export type DiabetesStatus = "yes" | "no";
export type BMIBand = "under" | "normal" | "over" | "obese";

export interface ProductRow {
  ProductID: number;
  LineOfBusiness: string;
  SeriesName: string;
  PlanName: string;
  Description: string | null;
}

export interface QuoteRateRow {
  RateVersionID: number;
  BaseRate: number;
  MortalityMultiplier: number;
}

export interface QuoteResult extends QuoteRateRow {
  applicationId: number;
  premium: number;
  ageBand: string;
  bmiBand: BMIBand;
}

export interface PriorQuoteRow {
  ApplicationID: number;
  QuotedPremium: number;
  QuotedRateVersionID: number;
}

export interface WellnessProgramRow {
  WellnessProgramID: number;
  ProgramName: string;
  PartnerGym: string | null;
  DiscountMaxPct: number | null;
}

export interface WellnessCandidate {
  ContractID: number;
  ContractNumber: string;
}

export interface WellnessDetail {
  ContractID: number;
  ContractNumber: string;
  ModalPremium: number | null;
  IssuedRateVersionID: number | null;
  ApplicationID: number;
  ProductID: number;
  FaceAmount: number;
  AgeBand: string;
  Gender: Gender;
  SmokingStatus: SmokingStatus;
  DiabetesStatus: DiabetesStatus;
  BMIBand: BMIBand;
  ActiveRateVersionID: number;
  BaseRate: number;
  RenewalDate: string;
  EnrollmentID: number | null;
  EnrollDate: string | null;
  QualifyingActivityCount: number;
  WellnessDiscountPct: number;
}

export interface PolicyRenewalRow {
  RenewalID: number;
  ContractID: number;
  RenewalDate: string;
  NewRateVersionID: number;
  WellnessDiscountPct: number | null;
  FinalPremium: number | null;
}

export interface RateVersionRow {
  RateVersionID: number;
  EffectiveDate: string;
  ExpiryDate: string | null;
  Status: "active" | "superseded" | "draft";
  PinnedContracts: number;
}

export interface RefreshRunRow {
  RunID: number;
  RunType: string;
  StartedAt: string;
  CompletedAt: string | null;
  Status: string;
  NewRateVersionID: number | null;
  Notes: string | null;
  Retrained: boolean;
  ObservedHash: string | null;
  ObservedByteSize: number | null;
}

export interface DataSourceStateRow {
  SourceStateID: number;
  SourcePath: string;
  ContentHash: string;
  ByteSize: number;
  ObservedAt: string;
  ObservedByRunID: number;
}

export interface BRFSSPrevalenceRow {
  AgeBand: string;
  Gender: Gender;
  MeanConditionalPrevalence: number;
}

export interface SSAMortalityRow {
  AgeBand: string;
  Gender: Gender;
  MortalityRate: number;
  LifeExpectancy: number | null;
}

export interface WellnessParticipationRow {
  ActivityYear: number;
  ParticipatingEnrollments: number;
  QualifyingActivities: number;
  TotalEnrollments: number;
}
