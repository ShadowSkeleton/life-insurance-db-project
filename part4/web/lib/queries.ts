// Jingrui Feng (jf4446) - database access queries
// Keep SQL here so the screens and route handlers remain readable and the
// project report can quote each access path directly.
export const ACTIVE_RATE_VERSION = `
  SELECT TOP (1) RateVersionID, EffectiveDate, ExpiryDate, Status
  FROM dbo.RATE_VERSION
  WHERE Status = 'active'
  ORDER BY EffectiveDate DESC, RateVersionID DESC;`;

export const PRODUCT_OPTIONS = `
  SELECT ProductID, LineOfBusiness, SeriesName, PlanName, Description
  FROM dbo.Product
  ORDER BY ProductID;`;

export const CUSTOMER_EXISTS = `
  SELECT CustomerID FROM dbo.Customer WHERE CustomerID = @customerId;`;

export const QUOTE_ACTIVE_RATE = `
  SELECT rv.RateVersionID, ra.BaseRate, rf.MortalityMultiplier
  FROM dbo.RATE_VERSION AS rv
  JOIN dbo.RISK_FACTOR AS rf ON rf.DerivedFromRunID = rv.CreatedByRunID
  JOIN dbo.RATE AS ra ON ra.RateVersionID = rv.RateVersionID
    AND ra.RiskFactorID = rf.RiskFactorID
  WHERE rv.Status = 'active' AND ra.ProductID = @productId
    AND rf.AgeBand = @ageBand AND rf.Gender = @gender
    AND rf.SmokingStatus = @smokingStatus AND rf.DiabetesStatus = @diabetesStatus
    AND rf.BMIBand = @bmiBand;`;

export const INSERT_APPLICATION = `
  INSERT dbo.APPLICATION (
    Customer_CustomerID, ProductID, ApplicationDate, ApplicantAge, Gender,
    SmokingStatus, DiabetesStatus, BMIValue, AgeBand, BMIBand, FaceAmount,
    QuotedRateVersionID, QuotedPremium, Status
  )
  OUTPUT INSERTED.ApplicationID
  VALUES (
    @customerId, @productId, CAST(GETDATE() AS DATE), @age, @gender,
    @smokingStatus, @diabetesStatus, @bmi, @ageBand, @bmiBand, @faceAmount,
    @rateVersionId, @premium, 'quoted'
  );`;

export const PRIOR_QUOTE_FOR_PROFILE = `
  SELECT TOP (1) ApplicationID, QuotedPremium, QuotedRateVersionID
  FROM dbo.APPLICATION
  WHERE ProductID = @productId AND ApplicantAge = @age AND Gender = @gender
    AND SmokingStatus = @smokingStatus AND DiabetesStatus = @diabetesStatus
    AND BMIValue = @bmi AND FaceAmount = @faceAmount
    AND QuotedRateVersionID <> @rateVersionId AND QuotedPremium IS NOT NULL
  ORDER BY ApplicationID DESC;`;

export const APPLICATION_FOR_BIND = `
  SELECT ApplicationID, ProductID, QuotedRateVersionID, QuotedPremium
  FROM dbo.APPLICATION WHERE ApplicationID = @applicationId AND Status = 'quoted';`;

export const NEXT_CONTRACT_ID = `
  SELECT ISNULL(MAX(ContractID), 0) + 1 AS ContractID
  FROM dbo.Contract WITH (UPDLOCK, HOLDLOCK);`;

export const INSERT_BOUND_CONTRACT = `
  INSERT dbo.Contract (
    ContractNumber, ActivityStatus, ModalPremium, InForceFlag, ContractID,
    Product_ProductID, IssuedRateVersionID, EffectiveDate, ApplicationID
  )
  VALUES (
    @contractNumber, 'Active', @premium, 'Y', @contractId, @productId,
    @rateVersionId, CAST(GETDATE() AS DATE), @applicationId
  );`;

export const MARK_APPLICATION_BOUND = `
  UPDATE dbo.APPLICATION SET Status = 'bound' WHERE ApplicationID = @applicationId;`;

export const WELLNESS_CONTRACTS = `
  SELECT TOP (40) c.ContractID, c.ContractNumber
  FROM dbo.Contract AS c
  JOIN dbo.WELLNESS_ENROLLMENT AS we ON we.ContractID = c.ContractID
  JOIN dbo.APPLICATION AS a ON a.ApplicationID = c.ApplicationID
  ORDER BY c.ContractID;`;

export const WELLNESS_PROGRAM_OPTIONS = `
  SELECT WellnessProgramID, ProgramName, PartnerGym, DiscountMaxPct
  FROM dbo.WELLNESS_PROGRAM
  ORDER BY WellnessProgramID;`;

export const WELLNESS_POLICY = `
  SELECT c.ContractID, c.ContractNumber, c.ModalPremium, c.IssuedRateVersionID,
         a.ApplicationID, a.ProductID, a.FaceAmount, a.AgeBand, a.Gender,
         a.SmokingStatus, a.DiabetesStatus, a.BMIBand,
         we.EnrollmentID, CONVERT(VARCHAR(10), we.EnrollDate, 23) AS EnrollDate
  FROM dbo.Contract AS c
  JOIN dbo.APPLICATION AS a ON a.ApplicationID = c.ApplicationID
  LEFT JOIN dbo.WELLNESS_ENROLLMENT AS we ON we.ContractID = c.ContractID
  WHERE c.ContractID = @contractId;`;

export const ACTIVE_PROFILE_RATE = `
  SELECT rv.RateVersionID AS ActiveRateVersionID, ra.BaseRate
  FROM dbo.RATE_VERSION AS rv
  JOIN dbo.RISK_FACTOR AS rf ON rf.DerivedFromRunID = rv.CreatedByRunID
  JOIN dbo.RATE AS ra ON ra.RateVersionID = rv.RateVersionID AND ra.RiskFactorID = rf.RiskFactorID
  WHERE rv.Status = 'active' AND ra.ProductID = @productId AND rf.AgeBand = @ageBand
    AND rf.Gender = @gender AND rf.SmokingStatus = @smokingStatus
    AND rf.DiabetesStatus = @diabetesStatus AND rf.BMIBand = @bmiBand;`;

// Renewal keeps Contract as the issue-time record. This context intentionally
// uses a LEFT JOIN to distinguish a missing application from a missing policy.
export const RENEWAL_POLICY = `
  SELECT c.ContractID, c.ContractNumber, c.ModalPremium, c.IssuedRateVersionID,
         a.ApplicationID, a.ProductID, a.FaceAmount, a.AgeBand, a.Gender,
         a.SmokingStatus, a.DiabetesStatus, a.BMIBand,
         we.EnrollmentID
  FROM dbo.Contract AS c
  LEFT JOIN dbo.APPLICATION AS a ON a.ApplicationID = c.ApplicationID
  LEFT JOIN dbo.WELLNESS_ENROLLMENT AS we ON we.ContractID = c.ContractID
  WHERE c.ContractID = @contractId;`;

export const POLICY_RENEWAL_FOR_CONTRACT_DATE = `
  SELECT TOP (1) RenewalID, ContractID,
         CONVERT(VARCHAR(10), RenewalDate, 23) AS RenewalDate,
         NewRateVersionID, WellnessDiscountPct, FinalPremium
  FROM dbo.POLICY_RENEWAL
  WHERE ContractID = @contractId AND RenewalDate = @renewalDate
  ORDER BY RenewalID DESC;`;

// Lock the ContractID/RenewalDate range because the inherited schema has no
// unique constraint for this business key.
export const POLICY_RENEWAL_EXISTS_FOR_UPDATE = `
  SELECT TOP (1) RenewalID
  FROM dbo.POLICY_RENEWAL WITH (UPDLOCK, HOLDLOCK)
  WHERE ContractID = @contractId AND RenewalDate = @renewalDate;`;

export const INSERT_POLICY_RENEWAL = `
  INSERT dbo.POLICY_RENEWAL (
    ContractID, RenewalDate, NewRateVersionID, WellnessDiscountPct, FinalPremium
  )
  OUTPUT INSERTED.RenewalID, INSERTED.ContractID, INSERTED.RenewalDate,
         INSERTED.NewRateVersionID, INSERTED.WellnessDiscountPct, INSERTED.FinalPremium
  VALUES (
    @contractId, @renewalDate, @newRateVersionId, @wellnessDiscountPct, @finalPremium
  );`;

// The indexed view is annual. NOEXPAND is required because SQL Server cannot
// prove that the application's yearly question equals the view automatically.
export const WELLNESS_YEAR_ACTIVITY = `
  SELECT COALESCE(SUM(QualifyingActivityCount), 0) AS QualifyingActivityCount
  FROM dbo.vWellnessActivityEnrollmentYear WITH (NOEXPAND)
  WHERE EnrollmentID = @enrollmentId AND ActivityYear = @activityYear;`;

export const WELLNESS_CREDIT = `
  SELECT CASE
    WHEN COALESCE(AVG(CASE WHEN ImprovementPct > 0 AND MeasureDate < @renewalDate
                           THEN ImprovementPct END), 0) > 15.00 THEN 15.00
    ELSE COALESCE(AVG(CASE WHEN ImprovementPct > 0 AND MeasureDate < @renewalDate
                           THEN ImprovementPct END), 0)
  END AS WellnessDiscountPct
  FROM dbo.RISK_IMPROVEMENT
  WHERE EnrollmentID = @enrollmentId;`;

export const INSERT_WELLNESS_ACTIVITY = `
  INSERT dbo.WELLNESS_ACTIVITY (EnrollmentID, ActivityDate, ActivityType, VerifiedFlag)
  OUTPUT INSERTED.ActivityID
  VALUES (@enrollmentId, CAST(GETDATE() AS DATE), @activityType, 'Y');`;

export const NEXT_PROJECTED_RENEWAL_DATE = `
  SELECT CONVERT(VARCHAR(10), DATEADD(YEAR, 1, CAST(GETDATE() AS DATE)), 23) AS RenewalDate;`;

export const WELLNESS_ENROLLMENT_CONTEXT = `
  SELECT CONVERT(VARCHAR(10), we.EnrollDate, 23) AS EnrollDate,
         CONVERT(VARCHAR(10), DATEADD(YEAR, 1, CAST(GETDATE() AS DATE)), 23) AS RenewalDate
  FROM dbo.WELLNESS_ENROLLMENT AS we
  WHERE we.EnrollmentID = @enrollmentId;`;

export const ENROLLMENT_EXISTS_FOR_CONTRACT = `
  SELECT EnrollmentID FROM dbo.WELLNESS_ENROLLMENT WHERE ContractID = @contractId;`;

export const WELLNESS_PROGRAM_EXISTS = `
  SELECT WellnessProgramID FROM dbo.WELLNESS_PROGRAM WHERE WellnessProgramID = @wellnessProgramId;`;

export const INSERT_WELLNESS_ENROLLMENT = `
  INSERT dbo.WELLNESS_ENROLLMENT (ContractID, WellnessProgramID, EnrollDate, Status)
  OUTPUT INSERTED.EnrollmentID
  VALUES (@contractId, @wellnessProgramId, @enrollDate, 'Active');`;

export const INSERT_RISK_IMPROVEMENT = `
  INSERT dbo.RISK_IMPROVEMENT (
    EnrollmentID, MeasureDate, MeasureType, MeasureValue, BaselineValue, ImprovementPct
  )
  OUTPUT INSERTED.ImprovementID
  VALUES (@enrollmentId, @measureDate, @measureType, @measureValue, @baselineValue, @improvementPct);`;

export const RATE_VERSION_HISTORY = `
  SELECT rv.RateVersionID, CONVERT(VARCHAR(10), rv.EffectiveDate, 23) AS EffectiveDate,
         CONVERT(VARCHAR(10), rv.ExpiryDate, 23) AS ExpiryDate, rv.Status,
         COUNT(c.ContractID) AS PinnedContracts
  FROM dbo.RATE_VERSION AS rv
  LEFT JOIN dbo.Contract AS c ON c.IssuedRateVersionID = rv.RateVersionID
  GROUP BY rv.RateVersionID, rv.EffectiveDate, rv.ExpiryDate, rv.Status
  ORDER BY rv.RateVersionID;`;

export const REFRESH_RUN_HISTORY = `
  SELECT r.RunID, r.RunType, CONVERT(VARCHAR(10), r.StartedAt, 23) AS StartedAt,
         CONVERT(VARCHAR(10), r.CompletedAt, 23) AS CompletedAt, r.Status,
         r.NewRateVersionID, r.Notes,
         CAST(CASE WHEN s.SourceStateID IS NULL THEN 0 ELSE 1 END AS bit) AS Retrained,
         s.ContentHash AS ObservedHash, s.ByteSize AS ObservedByteSize
  FROM dbo.DATA_REFRESH_RUN AS r
  LEFT JOIN dbo.DATA_SOURCE_STATE AS s ON s.ObservedByRunID = r.RunID
  ORDER BY r.RunID DESC;`;

export const DATA_SOURCE_STATE_HISTORY = `
  SELECT SourceStateID, SourcePath, ContentHash, ByteSize,
         CONVERT(VARCHAR(19), ObservedAt, 120) AS ObservedAt,
         ObservedByRunID
  FROM dbo.DATA_SOURCE_STATE
  ORDER BY SourceStateID DESC;`;

export const ANALYTICS_BRFSS_PREVALENCE = `
  SELECT AgeBand, Gender,
         CAST(AVG(PrevalenceRate) AS DECIMAL(6,4)) AS MeanConditionalPrevalence
  FROM dbo.STG_BRFSS
  WHERE DiabetesStatus = 'yes' AND PrevalenceRate IS NOT NULL
  GROUP BY AgeBand, Gender
  ORDER BY CASE AgeBand
    WHEN '18-24' THEN 1 WHEN '25-29' THEN 2 WHEN '30-34' THEN 3
    WHEN '35-39' THEN 4 WHEN '40-44' THEN 5 WHEN '45-49' THEN 6
    WHEN '50-54' THEN 7 WHEN '55-59' THEN 8 WHEN '60-64' THEN 9
    WHEN '65-69' THEN 10 WHEN '70-74' THEN 11 WHEN '75-79' THEN 12
    WHEN '80-99' THEN 13 END, Gender;`;

export const ANALYTICS_SSA_MORTALITY = `
  SELECT AgeBand, Gender, MortalityRate, LifeExpectancy
  FROM dbo.STG_MORTALITY
  WHERE SourceYear = 2023 AND ConditionFlag = 'BASELINE'
  ORDER BY TRY_CONVERT(INT, AgeBand), Gender;`;

export const ANALYTICS_WELLNESS_PARTICIPATION = `
  SELECT view_data.ActivityYear,
         COUNT_BIG(DISTINCT view_data.EnrollmentID) AS ParticipatingEnrollments,
         SUM(view_data.QualifyingActivityCount) AS QualifyingActivities,
         (SELECT COUNT_BIG(*) FROM dbo.WELLNESS_ENROLLMENT) AS TotalEnrollments
  FROM dbo.vWellnessActivityEnrollmentYear AS view_data WITH (NOEXPAND)
  GROUP BY view_data.ActivityYear
  ORDER BY view_data.ActivityYear;`;
