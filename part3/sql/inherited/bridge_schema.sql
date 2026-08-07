-- Jingrui Feng (jf4446) - database systems project part 2 - define health data bridge tables

-- ============================================================
-- BRIDGE / HYBRID SCHEMA  (life insurance + external health data)
-- Target: Azure SQL Database (SQL Server dialect)
-- Extends the optimized 18-table base schema.
-- Satisfies Prof Franchitti's 3 requirements (see comments).
-- ============================================================

-- ------------------------------------------------------------
-- LAYER A: DATA LAKE STAGING (Data)
-- Thin mirrors of curated slices from Blob Storage datasets.
-- ------------------------------------------------------------
CREATE TABLE STG_BRFSS (
    StgBRFSSID        INT IDENTITY(1,1) NOT NULL,
    SourceYear        INT            NOT NULL,
    AgeBand           VARCHAR(10)    NOT NULL,
    Gender            VARCHAR(1)     NOT NULL,
    SmokingStatus     VARCHAR(10)    NULL,
    DiabetesStatus    VARCHAR(10)    NULL,
    BMIBand           VARCHAR(10)    NULL,
    ExerciseFreq      VARCHAR(10)    NULL,
    PrevalenceRate    NUMERIC(6,4)   NULL,
    LoadDate          DATE           NOT NULL,
    SourceFile        VARCHAR(255)   NULL,
    CONSTRAINT STG_BRFSS_PK PRIMARY KEY (StgBRFSSID)
);

CREATE TABLE STG_NHANES (
    StgNHANESID       INT IDENTITY(1,1) NOT NULL,
    SourceCycle       VARCHAR(10)    NOT NULL,
    AgeBand           VARCHAR(10)    NOT NULL,
    Gender            VARCHAR(1)     NOT NULL,
    DiabetesBiomarker VARCHAR(20)    NULL,
    BMIMeasured       NUMERIC(5,2)   NULL,
    LoadDate          DATE           NOT NULL,
    SourceFile        VARCHAR(255)   NULL,
    CONSTRAINT STG_NHANES_PK PRIMARY KEY (StgNHANESID)
);

CREATE TABLE STG_MORTALITY (
    StgMortalityID    INT IDENTITY(1,1) NOT NULL,
    SourceYear        INT            NOT NULL,
    AgeBand           VARCHAR(10)    NOT NULL,
    Gender            VARCHAR(1)     NOT NULL,
    ConditionFlag     VARCHAR(10)    NULL,
    MortalityRate     NUMERIC(8,6)   NULL,
    LifeExpectancy    NUMERIC(5,2)   NULL,
    LoadDate          DATE           NOT NULL,
    SourceFile        VARCHAR(255)   NULL,
    CONSTRAINT STG_MORTALITY_PK PRIMARY KEY (StgMortalityID)
);

-- ------------------------------------------------------------
-- LAYER D: ASYNC MECHANISM  (Req #1)
-- Declared before RATE_VERSION/RISK_FACTOR because they FK to it.
-- Each run reads staging, rebuilds risk factors, issues a rate version.
-- ------------------------------------------------------------
CREATE TABLE DATA_REFRESH_RUN (
    RunID             INT IDENTITY(1,1) NOT NULL,
    RunType           VARCHAR(20)    NOT NULL,   -- scheduled/manual
    StartedAt         DATE           NOT NULL,
    CompletedAt       DATE           NULL,
    Status            VARCHAR(10)    NOT NULL,   -- success/failed/running
    SourceDatasets    VARCHAR(255)   NULL,
    NewRateVersionID  INT            NULL,       -- set after version created
    Notes             VARCHAR(255)   NULL,
    CONSTRAINT DATA_REFRESH_RUN_PK PRIMARY KEY (RunID)
);

-- ------------------------------------------------------------
-- LAYER B: RISK FACTOR (Information)
-- Bands -> mortality multiplier, derived by an async run.
-- ------------------------------------------------------------
CREATE TABLE RISK_FACTOR (
    RiskFactorID        INT IDENTITY(1,1) NOT NULL,
    AgeBand             VARCHAR(10)  NOT NULL,
    Gender              VARCHAR(1)   NOT NULL,
    SmokingStatus       VARCHAR(10)  NULL,
    DiabetesStatus      VARCHAR(10)  NULL,
    BMIBand             VARCHAR(10)  NULL,
    MortalityMultiplier NUMERIC(6,3) NOT NULL,   -- 1.00 = baseline
    DerivedFromRunID    INT          NOT NULL,
    CONSTRAINT RISK_FACTOR_PK PRIMARY KEY (RiskFactorID),
    CONSTRAINT RISK_FACTOR_RUN_FK FOREIGN KEY (DerivedFromRunID)
        REFERENCES DATA_REFRESH_RUN (RunID),
    CONSTRAINT RISK_FACTOR_UN UNIQUE
        (AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, DerivedFromRunID)
);

-- ------------------------------------------------------------
-- LAYER C: RATE  (Knowledge)  (Req #2 - effective-dated)
-- ------------------------------------------------------------
CREATE TABLE RATE_VERSION (
    RateVersionID     INT IDENTITY(1,1) NOT NULL,
    EffectiveDate     DATE           NOT NULL,
    ExpiryDate        DATE           NULL,       -- null = current
    Status            VARCHAR(10)    NOT NULL,   -- active/superseded/draft
    CreatedByRunID    INT            NULL,
    CONSTRAINT RATE_VERSION_PK PRIMARY KEY (RateVersionID),
    CONSTRAINT RATE_VERSION_RUN_FK FOREIGN KEY (CreatedByRunID)
        REFERENCES DATA_REFRESH_RUN (RunID)
);

CREATE TABLE RATE (
    RateID            INT IDENTITY(1,1) NOT NULL,
    RateVersionID     INT            NOT NULL,
    RiskFactorID      INT            NOT NULL,
    ProductID         INT            NOT NULL,   -- FK to base Product table
    BaseRate          NUMERIC(12,2)  NOT NULL,
    CONSTRAINT RATE_PK PRIMARY KEY (RateID),
    CONSTRAINT RATE_VERSION_FK FOREIGN KEY (RateVersionID)
        REFERENCES RATE_VERSION (RateVersionID),
    CONSTRAINT RATE_RISKFACTOR_FK FOREIGN KEY (RiskFactorID)
        REFERENCES RISK_FACTOR (RiskFactorID)
    -- NOTE: add RATE_PRODUCT_FK referencing Product(ProductID) after the
    -- base schema is deployed (see post-deploy section).
);

-- Backfill the async run's pointer to the version it created.
ALTER TABLE DATA_REFRESH_RUN
    ADD CONSTRAINT DRR_RATEVERSION_FK FOREIGN KEY (NewRateVersionID)
        REFERENCES RATE_VERSION (RateVersionID);

-- ------------------------------------------------------------
-- LAYER E: WELLNESS LOOPBACK  (Req #3)
-- ------------------------------------------------------------
CREATE TABLE WELLNESS_PROGRAM (
    WellnessProgramID INT IDENTITY(1,1) NOT NULL,
    ProgramName       VARCHAR(60)    NOT NULL,
    PartnerGym        VARCHAR(60)    NULL,
    DiscountMaxPct    NUMERIC(5,2)   NULL,
    CONSTRAINT WELLNESS_PROGRAM_PK PRIMARY KEY (WellnessProgramID)
);

CREATE TABLE WELLNESS_ENROLLMENT (
    EnrollmentID      INT IDENTITY(1,1) NOT NULL,
    ContractID        INT            NOT NULL,   -- FK to base Contract
    WellnessProgramID INT            NOT NULL,
    EnrollDate        DATE           NOT NULL,
    Status            VARCHAR(10)    NOT NULL,
    CONSTRAINT WELLNESS_ENROLLMENT_PK PRIMARY KEY (EnrollmentID),
    CONSTRAINT WENROLL_PROGRAM_FK FOREIGN KEY (WellnessProgramID)
        REFERENCES WELLNESS_PROGRAM (WellnessProgramID)
    -- NOTE: add WENROLL_CONTRACT_FK referencing Contract(ContractID) post-deploy.
);

CREATE TABLE WELLNESS_ACTIVITY (
    ActivityID        INT IDENTITY(1,1) NOT NULL,
    EnrollmentID      INT            NOT NULL,
    ActivityDate      DATE           NOT NULL,
    ActivityType      VARCHAR(20)    NULL,
    VerifiedFlag      CHAR(1)        NULL,
    CONSTRAINT WELLNESS_ACTIVITY_PK PRIMARY KEY (ActivityID),
    CONSTRAINT WACT_ENROLL_FK FOREIGN KEY (EnrollmentID)
        REFERENCES WELLNESS_ENROLLMENT (EnrollmentID)
);

CREATE TABLE RISK_IMPROVEMENT (
    ImprovementID     INT IDENTITY(1,1) NOT NULL,
    EnrollmentID      INT            NOT NULL,
    MeasureDate       DATE           NOT NULL,
    MeasureType       VARCHAR(20)    NOT NULL,   -- BMI, smoking, exercise
    MeasureValue      NUMERIC(8,2)   NULL,
    BaselineValue     NUMERIC(8,2)   NULL,
    ImprovementPct    NUMERIC(5,2)   NULL,
    CONSTRAINT RISK_IMPROVEMENT_PK PRIMARY KEY (ImprovementID),
    CONSTRAINT RIMP_ENROLL_FK FOREIGN KEY (EnrollmentID)
        REFERENCES WELLNESS_ENROLLMENT (EnrollmentID)
);

-- ------------------------------------------------------------
-- POLICY RENEWAL  (Req #3 - renewals re-priced, wellness offset)
-- ------------------------------------------------------------
CREATE TABLE POLICY_RENEWAL (
    RenewalID           INT IDENTITY(1,1) NOT NULL,
    ContractID          INT          NOT NULL,   -- FK to base Contract
    RenewalDate         DATE         NOT NULL,
    NewRateVersionID    INT          NOT NULL,
    WellnessDiscountPct NUMERIC(5,2) NULL,
    FinalPremium        NUMERIC(12,2) NULL,
    CONSTRAINT POLICY_RENEWAL_PK PRIMARY KEY (RenewalID),
    CONSTRAINT PRENEW_RATEVERSION_FK FOREIGN KEY (NewRateVersionID)
        REFERENCES RATE_VERSION (RateVersionID)
    -- NOTE: add PRENEW_CONTRACT_FK referencing Contract(ContractID) post-deploy.
);

-- ============================================================
-- POST-DEPLOY: run AFTER the base schema (Contract, Product) exists.
-- These wire the bridge into the base schema.
-- ============================================================
-- 1) Add the rate-version pin to Contract (Req #2: freeze existing policies)
-- ALTER TABLE Contract
--     ADD IssuedRateVersionID INT NULL;
-- ALTER TABLE Contract
--     ADD CONSTRAINT CONTRACT_RATEVERSION_FK FOREIGN KEY (IssuedRateVersionID)
--         REFERENCES RATE_VERSION (RateVersionID);
--
-- 2) Cross-schema FKs from bridge to base
-- ALTER TABLE RATE
--     ADD CONSTRAINT RATE_PRODUCT_FK FOREIGN KEY (ProductID)
--         REFERENCES Product (ProductID);
-- ALTER TABLE WELLNESS_ENROLLMENT
--     ADD CONSTRAINT WENROLL_CONTRACT_FK FOREIGN KEY (ContractID)
--         REFERENCES Contract (ContractID);
-- ALTER TABLE POLICY_RENEWAL
--     ADD CONSTRAINT PRENEW_CONTRACT_FK FOREIGN KEY (ContractID)
--         REFERENCES Contract (ContractID);
