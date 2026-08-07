# Jingrui Feng (jf4446) - database systems project part 3 - project guide

# Part 3: Physical Design and Analytics

I use this directory for Part 3 of the life-insurance database systems project.
Part 3 adds physical database design, public-health staging, machine learning,
rate publication, business workflow documentation, and a local demonstration
application.

`data/curated/`, `data/synthetic/small/`, `sql/inherited/`, and
`docs/inherited/` came from the frozen Part 2 submission. I read them as
reference artifacts and do not modify them. Part 3 generated data is in
`data/processed/`, `data/synthetic/large/`, and `outputs/`. Credentials belong
only in the untracked `.env` file.

## Verified local state

The local SQL Server database is `LifeInsuranceP3` in Docker container
`dbsys-p3-mssql`. It has 43 user tables. The principal populated tables contain
50,000 `Customer` rows, 60,002 `Contract` rows, 90,000 `ContractParty` rows,
300,000 `Invoice` rows, 1,000,003 `WELLNESS_ACTIVITY` rows, 24,001
`WELLNESS_ENROLLMENT` rows, 48,002 `RISK_IMPROVEMENT` rows, 50,000
`STG_BRFSS_RECORD` rows, 8,153 `STG_NHANES` rows, and 109 `STG_MORTALITY` rows.

The database has eleven `RATE_VERSION` rows. Version 11 is active. Five
successful refresh runs produced 3,120 `RISK_FACTOR` rows and 46,800 `RATE`
rows. The BRFSS diabetes risk-stratification model is trained and documented in
`notebooks/diabetes_risk_model.ipynb` and `docs/ml_model_summary.md`. The local
Next.js application is in `web/` and demonstrates quoting, binding, rate
refresh, wellness enrollment, activity, and biometric screening.

Part 3 adds nullable `Contract.EffectiveDate` and `Contract.ExpiryDate` through
`sql/physical/schema_amendments.sql`. It uses `EffectiveDate` as a documented
simplification of application date, issue date, and effective date.

## Verified Azure state

Azure SQL Database now has the same 43-table Part 3 schema, generated volume
data, staged public-health data, indexes, yearly partition schemes, and indexed
view as the local deployment. Its Azure-only physical deployment keeps all
partitions in PRIMARY because Azure SQL single databases do not expose the
local filegroup layout. The detailed deployment record is
`docs/azure_deployment.md`.

Azure contains 50,000 Customer rows, 60,000 Contract rows, 300,000 Invoice
rows, 1,000,000 WELLNESS_ACTIVITY rows, 1,872 RISK_FACTOR rows, 28,080 RATE
rows, and three successful DATA_REFRESH_RUN rows. RATE_VERSION 9 is active.
The three Azure publications used WONDER cohort 2023, loading 1.50, and
undiagnosed fraction 0.20. No existing Contract references versions 7, 8, or 9.
The local database is correctly on rate version 11 because it received
additional demonstration runs after its Azure deployment diverged.

The Azure volume load used Blob Storage for transfer, but the identity-order
temporary-stage BULK INSERT hit provider error 7301. The verified Python
network-driver fallback took 11 minutes 28 seconds, against 5 seconds locally.
Do not treat the Azure environment as a copy of local results. It is a separate
deployment with its own rate publication and logical-read evidence in
`outputs/azure/`.

## Run locally

Install Python dependencies with:

```sh
python -m pip install -r requirements.txt
```

Set the local `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`,
`MSSQL_SA_PASSWORD`, and `MSSQL_DATABASE` values in `.env`. Start a SQL Server
2022 container with the generated files mounted read-only at `/data`. The
following mount is portable when run from this directory:

```sh
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=${MSSQL_SA_PASSWORD}" \
  -p 1433:1433 --name dbsys-p3-mssql --platform linux/amd64 \
  --label project=dbsys-p3 \
  -v dbsys-p3-data:/var/opt/mssql \
  -v "$PWD/data/synthetic/large:/data:ro" \
  -d mcr.microsoft.com/mssql/server:2022-latest
```

For a clean local database, follow this sequence:

1. Copy the inherited schema files and Part 3 amendment files into the
   container path required by `sql/load/deploy_local.sql`, then run that script
   with `sqlcmd`.
2. Run `sql/load/load_volume_data.sql` following the identity checks in
   `sql/load/load_order.md`.
3. Load the initial `APPLICATION` data with
   `sql/load/load_application_local.sql`.
4. Run `python python/etl/load_staging.py` and then execute
   `sql/load/load_staging_local.sql`.
5. Build the supervised frame with
   `python python/etl/build_training_frame.py` and train with
   `python python/ml/train_diabetes_risk_model.py`.
6. Publish a local rate version with
   `python python/etl/run_rate_refresh.py --wonder-cohort-source-year 2023`.

From `web/`, run `npm install` and `npm run dev`, then open
`http://localhost:3000/quote`. The application reads the same parent `.env`
file and invokes the existing Python refresh script for rate publication.

## Physical-design measurement

The container runs the x86_64 SQL Server image under Docker Desktop Rosetta on
Apple Silicon. I compare physical-design alternatives with logical reads from
`SET STATISTICS IO ON` and execution-plan shape. I do not use elapsed time as a
cross-platform performance result under emulation.

## Local operations

```sh
docker start dbsys-p3-mssql
docker stop dbsys-p3-mssql
docker logs dbsys-p3-mssql | tail -30
docker exec dbsys-p3-mssql ls /data
```

The generated volume CSV files use CRLF line endings. The local bulk-load
scripts use `ROWTERMINATOR = '0x0d0a'` and `KEEPNULLS` where nullable fields
need preservation.

Remove the local environment after the project with:

```sh
docker rm -f $(docker ps -aq --filter label=project=dbsys-p3)
docker volume rm dbsys-p3-data
docker rmi mcr.microsoft.com/mssql/server:2022-latest
```
