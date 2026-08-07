-- Jingrui Feng (jf4446) - database systems project part 3 - brfss summary refresher
-- Rebuild only the SQL-derived BRFSS Information-layer summary from the
-- existing STG_BRFSS_RECORD Data-layer rows.
SET NOCOUNT ON;
TRUNCATE TABLE dbo.STG_BRFSS;

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
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
             ExerciseFreq, LoadDate, SourceFile
) AS outcome
JOIN (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
           LoadDate, SourceFile, COUNT_BIG(*) AS ProfileRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
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
