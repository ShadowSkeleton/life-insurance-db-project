-- Jingrui Feng (jf4446) - database systems project part 3 - azure blob lake queries
-- Azure SQL data virtualization over curated files in Blob Storage.
-- P3BlobDataSource points at the existing datalake container.

-- Azure SQL Database's HTTPS connector does not support schema-aware CSV
-- OPENROWSET. It supports SINGLE_CLOB, so these queries parse the required
-- fields in place. Synapse serverless would provide native typed CSV parsing.

-- QL1. Aggregate the BRFSS curated file without ingesting it.
WITH lake_file AS (
    SELECT BulkColumn AS Contents
    FROM OPENROWSET(
        BULK 'part3-analytics/curated/brfss_2024_life_risk_sample_50000.csv',
        DATA_SOURCE = 'P3BlobDataSource',
        SINGLE_CLOB
    ) AS source_file
), lines AS (
    SELECT TRIM(REPLACE(value, CHAR(13), '')) AS line
    FROM lake_file CROSS APPLY STRING_SPLIT(Contents, CHAR(10))
)
SELECT TRY_CONVERT(INT, TRY_CONVERT(DECIMAL(4, 1),
       LEFT(line, CHARINDEX(',', line + ',') - 1))) AS DiabetesResponse,
       COUNT_BIG(*) AS Respondents
FROM lines
WHERE line NOT LIKE 'DIABETE4,%'
  AND TRY_CONVERT(INT, TRY_CONVERT(DECIMAL(4, 1),
      LEFT(line, CHARINDEX(',', line + ',') - 1))) IN (1, 2, 3, 4)
GROUP BY TRY_CONVERT(INT, TRY_CONVERT(DECIMAL(4, 1),
         LEFT(line, CHARINDEX(',', line + ',') - 1)))
ORDER BY DiabetesResponse;

-- QL2. Join a Blob-resident SSA file to the staged Azure SQL baseline rows.
WITH lake_file AS (
    SELECT BulkColumn AS Contents
    FROM OPENROWSET(
        BULK 'part3-analytics/curated/ssa_period_life_table_2023.csv',
        DATA_SOURCE = 'P3BlobDataSource',
        SINGLE_CLOB
    ) AS source_file
), lines AS (
    SELECT TRIM(REPLACE(value, CHAR(13), '')) AS line
    FROM lake_file CROSS APPLY STRING_SPLIT(Contents, CHAR(10))
), parsed AS (
    SELECT MAX(CASE WHEN token.[key] = '0' THEN TRY_CONVERT(INT, token.value) END) AS age,
           MAX(CASE WHEN token.[key] = '1' THEN TRY_CONVERT(DECIMAL(12, 8), token.value) END)
               AS male_death_probability
    FROM lines
    CROSS APPLY OPENJSON(CONCAT('["', REPLACE(line, ',', '","'), '"]')) AS token
    WHERE line NOT LIKE 'age,%'
    GROUP BY line
)
SELECT lake.age, lake.male_death_probability, staged.AgeBand,
       staged.MortalityRate AS StagedMortalityRate
FROM parsed AS lake
JOIN dbo.STG_MORTALITY AS staged
  ON staged.SourceYear = 2023
 AND staged.ConditionFlag = 'BASELINE'
 AND staged.Gender = 'M'
 AND staged.AgeBand = '45-49'
WHERE lake.age BETWEEN 45 AND 49
ORDER BY lake.age;
