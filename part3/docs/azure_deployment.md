# Jingrui Feng (jf4446) - database systems project part 3 - azure sql deployment

# Azure SQL deployment

I deployed the Part 3 environment to Azure SQL Database on 2026-08-03. The
target began with the Part 2 schema and 6,336 KB of allocated table and index
storage. The completed deployment uses 254,640 KB, or about 0.76 percent of
the 32 GB limit.

## Deployment order

I first verified the inherited 41-table schema, then applied the Part 3
Contract date amendments, the APPLICATION and STG_BRFSS_RECORD staging
amendments, and the generated volume data. The data load preceded the public
health staging data, the physical design, and the cloud refresh job. The final
database has 43 user tables.

The Azure load preserved the identity assumptions used by the bridge CSVs. The
network loader inserted explicit bridge identities in source row order and
verified the assigned ranges before dependent tables loaded. This included
WELLNESS_ENROLLMENT identities 1 through 24,000, which are referenced by the
one million WELLNESS_ACTIVITY rows, and RATE_VERSION seed identities 1 through
6, which are referenced by Contract.IssuedRateVersionID.

## Loading result and portability findings

I uploaded the generated CSVs to Blob Storage and configured an Azure external
data source successfully. A BULK INSERT into the temporary identity-order
staging table then returned provider error 7301. I used the Python network
driver fallback instead, retaining the same source order and identity checks.

Azure SQL required a database master key before it accepted the database scoped
credential for Blob Storage. Local SQL Server did not require that prerequisite.
This is a portability difference worth retaining in the report.

The Azure data load took 11 minutes 28 seconds, compared with 5 seconds on the
local container for the same data. The difference is attributable to the
network-driver fallback and its network round trips, rather than a difference
in input volume. The first driver process appeared to stall after 9,000
Contract rows because it blocked on its own output pipe. I checked
sys.dm_exec_requests and found no active write, which identified the process
state before I resumed from the verified completed point.

Azure SQL exposes only the PRIMARY filegroup. The deployment therefore created
the same yearly partition function and partition schemes as the local design,
but maps every partition to PRIMARY. It demonstrates partition elimination
without demonstrating filegroup-level placement or storage isolation.

## Cloud rate publication and Function automation

`python/etl/run_rate_refresh.py --azure` reads STG_MORTALITY and
STG_BRFSS_RECORD in Azure and reads the project model export
`outputs/model/predicted_risk_by_profile.csv`. The script now has a distinct
Azure connection path using AZURE_SQL_SERVER, AZURE_SQL_DATABASE,
AZURE_SQL_USER, and AZURE_SQL_PASSWORD. It retains the local Docker and BULK
INSERT path for local publication.

The initial Azure publication used WONDER cohort 2023, loading factor 1.50,
and undiagnosed fraction 0.20. It published RATE_VERSION 7 on 2026-08-03. The
deployed Azure Function later published versions 8 and 9 during controlled
verification on 2026-08-04. Each of the three runs created 624 RISK_FACTOR rows
and 9,360 RATE rows. Azure therefore holds 1,872 RISK_FACTOR rows, 28,080 RATE
rows, and three successful DATA_REFRESH_RUN rows. The Notes for each run record
the cohort, SSA baseline year, loading factor, undiagnosed fraction, smoking
and BMI judgment inputs, and model export.

Version 9 is the single active Azure version. Versions 7 and 8 are superseded.
No Contract row references versions 7, 8, or 9, so repeated publication did not
reprice existing policies. Contract counts by issued version remain 7,484,
8,437, 9,505, 10,526, 11,600, and 12,448 for versions 1 through 6. The local
database is on version 11 because it received additional demonstration runs and
is not intended to mirror the separate Azure refresh history.

The Function App is `func-dbp3-raterefresh`, a Linux Python 3.11 app on the
Consumption plan in Central US. Its monthly Azure Functions NCRONTAB schedule
is `0 0 2 1 * *`, the first day of every month at 02:00 UTC. The Function reads
the Blob model export and Azure staging data, then writes the refresh, factor,
rate-version, and rate tables without writing Contract.

The three relative-risk checks matched the local run exactly. The values were
1.396604722997 for 45-49 male, 1.250608026670 for 55-59 male, and
1.103290668452 for 80-99 male.

## Physical-design measurement

I measured each query twice with SET STATISTICS IO ON, discarded the first
execution, and retained the second. The detailed table-level evidence is in
`outputs/azure/results.csv`, with plan files in `outputs/azure/plans/`.

| Query | Local final reads | Azure reads | Azure access |
|---|---:|---:|---|
| Q1 | 5 | 5 | ContractParty index seek |
| Q4 | 7 | 7 | WELLNESS_ACTIVITY index seek |
| Q5 | 423 | 423 | WELLNESS_ACTIVITY index scan |
| Q8a count | 29 | 29 | Contract status index seek |
| Q8b count | 147 | 147 | Contract status index seek |
| Q8a retrieval | 1,424 | 3,090 | Contract clustered index scan |
| Q8b retrieval | 1,424 | 3,090 | Contract clustered index scan |

Q1, Q4, Q5, and the covered Q8 counts have the same logical-read results and
access choices locally and in Azure. Both noncovering Q8 retrieval variants are
clustered scans in both deployments. Azure reads more Contract pages because
its independently loaded clustered structure uses 3,090 pages, while the
local structure uses 1,424. This is a storage-layout difference, not an
optimizer claim that the noncovering status index became useful.

## Portal evidence captured

Six captured images are stored in `outputs/azure/screenshots/`: database
overview, table list, two query results, Function App overview, and timer
configuration. They document the deployed database and the monthly scheduled
refresh mechanism. The Azure SQL state shown in the report should identify
version 9 as active, with versions 7 and 8 superseded.
