-- Jingrui Feng (jf4446) - database systems project part 3 - local staging bulk loader
-- Local staging load. Python creates CSVs with explicit identity values and
-- copies them to /tmp/dbsys-p3-staging in dbsys-p3-mssql before this runs.
-- Staging outputs use CRLF, so every direct BULK INSERT names 0x0d0a.
SET NOCOUNT ON;
GO

TRUNCATE TABLE dbo.STG_BRFSS;
TRUNCATE TABLE dbo.STG_BRFSS_RECORD;
TRUNCATE TABLE dbo.STG_NHANES;
TRUNCATE TABLE dbo.STG_MORTALITY;
GO

BULK INSERT dbo.STG_BRFSS_RECORD FROM '/tmp/dbsys-p3-staging/STG_BRFSS_RECORD.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPIDENTITY, KEEPNULLS);
BULK INSERT dbo.STG_NHANES FROM '/tmp/dbsys-p3-staging/STG_NHANES.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPIDENTITY, KEEPNULLS);
BULK INSERT dbo.STG_MORTALITY FROM '/tmp/dbsys-p3-staging/STG_MORTALITY.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPIDENTITY, KEEPNULLS);
GO

-- DiabetesStatus is the outcome dimension. PrevalenceRate is therefore
-- P(DiabetesStatus | AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq).
-- Its rows sum to 1.0 (subject to NUMERIC(6,4) rounding) within every
-- five-factor profile. Records with a NULL in any profile or outcome field
-- are excluded.
INSERT dbo.STG_BRFSS
    (SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
     ExerciseFreq, PrevalenceRate, LoadDate, SourceFile)
SELECT outcome.SourceYear, outcome.AgeBand, outcome.Gender, outcome.SmokingStatus,
       outcome.DiabetesStatus, outcome.BMIBand, outcome.ExerciseFreq,
       CAST(CAST(outcome.OutcomeRows AS DECIMAL(18,8)) / profile.ProfileRows AS NUMERIC(6,4)),
       outcome.LoadDate, outcome.SourceFile
FROM (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
           ExerciseFreq, LoadDate, SourceFile, COUNT_BIG(*) AS OutcomeRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL
      AND Gender IS NOT NULL
      AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL
      AND BMIBand IS NOT NULL
      AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
             ExerciseFreq, LoadDate, SourceFile
) AS outcome
JOIN (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
           LoadDate, SourceFile, COUNT_BIG(*) AS ProfileRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL
      AND Gender IS NOT NULL
      AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL
      AND BMIBand IS NOT NULL
      AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
             LoadDate, SourceFile
) AS profile
  ON profile.SourceYear = outcome.SourceYear
 AND profile.AgeBand = outcome.AgeBand
 AND profile.Gender = outcome.Gender
 AND profile.SmokingStatus = outcome.SmokingStatus
 AND profile.BMIBand = outcome.BMIBand
 AND profile.ExerciseFreq = outcome.ExerciseFreq
 AND profile.LoadDate = outcome.LoadDate
 AND profile.SourceFile = outcome.SourceFile;
GO
