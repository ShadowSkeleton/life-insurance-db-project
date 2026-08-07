-- Jingrui Feng (jf4446) - database systems project part 3 - annual wellness indexed view
-- Corrected Increment 3: materialize verified wellness activity at annual
-- enrollment grain.  The renewal-credit process is annual, so ActivityYear
-- avoids the prior daily view's 245,170-row scan. SCHEMABINDING and COUNT_BIG
-- are mandatory SQL Server indexed-view requirements; the view uses no joins,
-- subqueries, or non-deterministic expressions.
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;
GO

IF OBJECT_ID(N'dbo.vWellnessActivityEnrollmentDaily', N'V') IS NOT NULL
    DROP VIEW dbo.vWellnessActivityEnrollmentDaily;
GO

CREATE VIEW dbo.vWellnessActivityEnrollmentYear
WITH SCHEMABINDING
AS
    SELECT wa.EnrollmentID,
           DATEPART(YEAR, wa.ActivityDate) AS ActivityYear,
           COUNT_BIG(*) AS QualifyingActivityCount
    FROM dbo.WELLNESS_ACTIVITY AS wa
    WHERE wa.VerifiedFlag = 'Y'
    GROUP BY wa.EnrollmentID, DATEPART(YEAR, wa.ActivityDate);
GO

-- Q5 and the renewal-credit calculation: ActivityYear leads because Q5 first
-- selects one annual cohort across all enrollments. The subsequent EnrollmentID
-- key also supports Q4's single enrollment within that year.
-- FILLFACTOR 80 reserves room for continuing activity inserts; this trades
-- storage density and indexed-view maintenance for analytical throughput.
CREATE UNIQUE CLUSTERED INDEX CIX_vWellnessActivityEnrollmentYear
ON dbo.vWellnessActivityEnrollmentYear (ActivityYear, EnrollmentID)
WITH (FILLFACTOR = 80);
GO
