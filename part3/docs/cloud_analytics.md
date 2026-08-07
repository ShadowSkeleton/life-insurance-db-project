# Jingrui Feng (jf4446) - database systems project part 3 - cloud analytics design

# Cloud Big Data analytics

I use Azure Blob Storage as the lake and Azure SQL Database as the relational
warehouse. I added direct lake inspection, a read-only analytics route, and a
deployed Azure Function for monthly rate publication. I did not create a Synapse
workspace because the existing storage account does not support the required
Synapse storage feature.

## Requirement mapping

| Verb | Implementation | Status and limitation |
|---|---|---|
| Extract | `OPENROWSET` reads BRFSS and SSA curated files from Blob Storage through `P3BlobDataSource`. | Built and measured. Azure SQL Database reads the files as `SINGLE_CLOB`, so the queries parse only the fields needed for inspection. Synapse serverless would provide native typed CSV parsing if it becomes feasible. |
| Filter | The lake queries filter diabetes response codes before aggregation and select source ages 45 through 49 before joining the staged baseline. | Built. This lets me assess a lake asset before I choose to ingest it. |
| Store | Blob Storage retains the model export and curated files. Azure SQL Database retains staging, rate versions, rates, and refresh audit history. | Built. Blob Storage is the lake and Azure SQL is the warehouse. |
| Analyze | `run_rate_refresh.py` is importable. The deployed Azure Function calls that one source of pricing logic with Azure staging data and a Blob-downloaded model export. | Deployed and verified. The timer runs on the first day of each month at 02:00 UTC; initial manual invocations verified publication. |
| Present | `/admin/analytics` reads Azure SQL and presents rate history, BRFSS prevalence, SSA baseline mortality, materialized wellness participation, and refresh history. | Built as a read-only application route. |

Querying lake files in place is useful before ingestion. I can inspect the
source, apply a narrow filter, and decide whether it belongs in the warehouse.
This is the discipline that keeps the lake from becoming a data swamp.

## Lake virtualization result

I uploaded the model export to
`datalake/part3-analytics/model/predicted_risk_by_profile.csv`. I also uploaded
the BRFSS and SSA curated files under `datalake/part3-analytics/curated/` for
the lake demonstration. `sql/physical/lake_queries.sql` contains the two
reproducible Azure SQL queries.

The BRFSS query aggregated the Blob-resident file in 2.337 seconds. It returned
7,120 diagnosed-diabetes responses, 380 gestational-only responses, 41,179 no
responses, and 1,222 pre-diabetes responses. The SSA query joined Blob source
ages 45 through 49 to the staged male 45-49 baseline in 0.314 seconds. The
source death probabilities were 0.003931, 0.004073, 0.004245, 0.004477, and
0.004795. The staged five-year-band mortality rate was 0.004302.

The existing Azure SQL HTTPS connector rejected schema-aware CSV `OPENROWSET`
syntax. It accepts `SINGLE_CLOB`, which is why the implemented queries use
`STRING_SPLIT` and `OPENJSON` to parse the required fields.

I refreshed the existing `P3BlobCredential` with a read and list only SAS for
the existing `datalake` container after the credential could no longer read a
verified Blob object. It expires on 2026-08-06. No new Azure resource was
created.

## Azure Functions deployment

`functions/rate_refresh/` contains the timer-triggered function package.
`function_app.py` downloads `predicted_risk_by_profile.csv` from Blob into a
temporary file and calls the existing `run()` function from the staged copy of
`python/etl/run_rate_refresh.py`. The function does not reimplement pricing.
The timer expression is `0 0 2 1 * *`. Azure Functions uses six-field
NCRONTAB order: second, minute, hour, day, month, and day of week. The
expression therefore runs on the first day of each month at 02:00 UTC.

The deployed Linux Python 3.11 Function App is named
`func-dbp3-raterefresh`. It runs in Central US on the Azure Functions
Consumption plan and reuses the existing `dbp2lakefeng` storage account in
East US. A monthly timer run is expected to remain within the Consumption
plan's free monthly grant. Azure automatically created Application Insights
for execution telemetry.

The Function App uses these application settings: `AZURE_SQL_SERVER`,
`AZURE_SQL_DATABASE`, `AZURE_SQL_USER`, `AZURE_SQL_PASSWORD`,
`AZURE_STORAGE_CONNECTION_STRING`, `AZURE_STORAGE_CONTAINER`,
`MODEL_BLOB_PATH`, `WONDER_COHORT_SOURCE_YEAR`, `LOADING_FACTOR`, and
`UNDIAGNOSED_FRACTION`. Credentials are application settings, not package
files. The configured pricing inputs are cohort 2023, loading 1.50, and
undiagnosed fraction 0.20.

The schedule is a configuration parameter, not a structural property of the
mechanism. If source-data cadence changed, or the designed streaming wellness
feed became operational, the same function could run more often without a code
change.

The design reason for a monthly cadence comes first. CDC WONDER mortality data,
SSA period life tables, and BRFSS survey data all publish annually. A daily
refresh would recompute identical rates from unchanged inputs on 364 days of a
typical year, which is a design flaw rather than a feature. Monthly execution is
generous relative to that publication cycle while still demonstrating a process
that runs without human intervention.

There is also an operational reason. Azure SQL Database uses a serverless tier
and can auto-pause when idle. A scheduled run wakes it, and serverless billing
therefore includes awake time rather than only the short query duration. Each
wake costs roughly the auto-pause delay regardless of how briefly the job runs.
A daily schedule would consume a substantial share of the monthly vCore-second
allowance on refreshes that have no new input to process.

The Function App is in Central US with Azure SQL, while the inherited Part 2
storage account holding the model export is in East US. Each run reads the model
CSV across regions, adding egress cost and latency. At a monthly cadence this
is negligible. Co-locating storage with compute is the correct refinement if
the cadence increases.

The deployment used a remote Linux x64 build. The Azure SQL firewall already
allowed Azure services. The successful first invocation published
`RATE_VERSION` 8, 624 `RISK_FACTOR` rows, and 9,360 `RATE` rows in 4.672
seconds. Two later diagnostic invocations also completed and published version
9, so version 9 is now the single active version. Both runs recorded their
cohort, loading, undiagnosed fraction, SSA baseline year, and external smoking
and BMI relativity inputs in `DATA_REFRESH_RUN.Notes`. No Contract references
either function-published version, so the asynchronous process did not reprice
in-force policies.

The model stays in Blob instead of the function deployment package. A model
retrain can therefore write a replacement prediction export to the lake and the
next timer run consumes it without a function redeployment. This separates
offline training from online rate publication and is the intended path for
automated retraining.

## Synapse feasibility

`dbp2lakefeng` is StorageV2 and hierarchical namespace is disabled. Synapse
serverless requires an ADLS Gen2 account with hierarchical namespace enabled.
I did not enable it because that change cannot be reversed. I also did not
create a second storage account or a Synapse workspace. Synapse is therefore a
documented option, not a deployed service.

## Designed streaming path

I designed, but did not deploy, a wellness streaming path. Gym check-ins would
enter Azure Event Hubs, Azure Stream Analytics would validate and aggregate the
events, and a controlled consumer would write verified events to
`WELLNESS_ACTIVITY`. The present wellness source arrives in batches and the
one-million-row synthetic history does not require a streaming tier.

I would revisit this design at sustained 10,000 verified check-ins per hour or
when a company requirement needs a check-in to affect renewal eligibility in
less than five minutes. Those are design thresholds, not observations about the
current data. Until then, Event Hubs and Stream Analytics remain future state.
