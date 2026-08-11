# Life Insurance Database Project

Database Systems, Summer 2026  
Jingrui Feng, jf4446

This repository contains an enterprise data architecture for a life insurance company, built across four course parts. It starts with an Oracle data model and ends with a workflow-based application where public health data can revise the rate book and reach a customer-facing quote.

## The three required mechanisms

1. An asynchronous mechanism revises pricing from external datasets. `POST /api/reprice` in `part4/web/app/api/reprice/route.ts` starts `part4/python/run_rate_refresh.py`. The refresh records `DATA_REFRESH_RUN`, detects source changes through `DATA_SOURCE_STATE`, and publishes `RISK_FACTOR`, `RATE_VERSION`, and `RATE`.
2. Pricing changes do not affect existing policyholders while new applicants get current rates. `POST /api/bind` writes `Contract.IssuedRateVersionID`. The repricing path writes no `Contract` row. New quotes read the active `RATE_VERSION` through `POST /api/quote`.
3. Renewals are repriced against new rates with wellness offsets. `POST /api/renew` reads the current active `RATE_VERSION`, calculates the credit, and writes `POLICY_RENEWAL`. It leaves the issued `Contract` record unchanged.

## Repository layout

```text
life-insurance-db-project/
├── part1/                         # Conceptual and logical data model submission
│   └── part1_1/                   # Oracle SQL Developer Data Modeler design files
├── part2/                         # Relational schema, source data, and synthetic loads
│   ├── curated/                   # Curated public-health extracts
│   ├── mockaroo/                  # Synthetic company data
│   ├── model/                     # Oracle Data Modeler relational model
│   ├── raw/                       # Downloaded public-source material and notes
│   └── screenshots/               # Part 2 database evidence
├── part3/                         # Physical design, analytics, Function, and deployment evidence
│   ├── data/                      # Curated, processed, and synthetic data
│   ├── diagrams/                  # Mermaid diagram sources and renders
│   ├── docs/                      # Design, deployment, and model documentation
│   ├── functions/                 # Azure Function rate-refresh package
│   ├── notebooks/                 # Model development notebooks
│   ├── outputs/                   # Published model and refresh outputs
│   ├── python/                    # ETL, training, and refresh code
│   ├── sql/                       # Deployment, load, and physical-design SQL
└── part4/                         # Retraining, renewal, application integration, and report
    ├── data/                      # Curated source copies, revisions, and processed data
    ├── diagrams/                  # Part 4 process and architecture diagrams
    ├── docs/                      # Part 4 design and measurement documents
    ├── outputs/                   # Model and refresh output files
    ├── python/                    # Retraining, staging, and refresh code
    ├── screenshots/               # Demonstration capture sequence
    ├── sql/                       # Part 4 schema amendments
    └── web/                       # Part 4 Next.js application
```

The tree omits `node_modules`, `.venv`, `.next`, generated Prisma client files, and `__pycache__` directories.

## What each part contains

### Part 1

Report: `part1/jingrui_feng_project_1.docx`  
Main artifacts: `part1/part1_1.dmd` and `part1/ER_Diagram.png`  
Part 1 produced the conceptual and logical entity relationship design.

### Part 2

Report: `part2/Feng_p2_report.docx`  
Main artifacts: `part2/schema_final.sql`, `part2/bridge_schema.sql`, `part2/model/Feng_p2.dmd`, `part2/build_curated.py`, and `part2/curated/`  
Part 2 produced the relational schema, bridge tables, curated public data, and deterministic synthetic company data.

### Part 3

Report: `part3/Feng_p3_report.docx`  
Main artifacts: `part3/sql/`, `part3/python/`, `part3/functions/`, `part3/docs/`, and `part3/diagrams/`  
Part 3 produced the physical database design, rate engine, Azure Function, workflow documentation, and Azure deployment evidence.

### Part 4

Report: `part4/Feng_p4_report.docx`  
Main artifacts: `part4/sql/`, `part4/python/`, `part4/web/`, `part4/docs/`, `part4/diagrams/`, and `part4/screenshots/`  
Part 4 produced source-change retraining, rate lineage, policy renewal, application integration, ORM measurement, and the final demonstration.

## Part 4 artifact index

| Artifact | Path | What it is |
| --- | --- | --- |
| Part 4 report | `part4/Feng_p4_report.docx` | Final Part 4 report and demonstration evidence. |
| Application design | `part4/docs/application_design.md` | Application layers, routes, transactions, and rejection paths. |
| Demonstration guide | `part4/docs/demo_guide.md` | The in-app demonstration sequence. |
| Model summary | `part4/docs/ml_model_summary.md` | Training, validation, and gate results. |
| Query optimization | `part4/docs/query_optimization.md` | Logical-read and execution-plan measurements. |
| Reference architecture v3 | `part4/docs/reference_architecture_v3.md` | Final architecture, governance, and operating model. |
| Retraining design | `part4/docs/retraining_module_design.md` | Change detection, validation gate, and lineage design. |
| Source-state amendment | `part4/sql/01_data_source_state.sql` | Creates `DATA_SOURCE_STATE` and its refresh-run foreign key. |
| Renewal uniqueness amendment | `part4/sql/02_policy_renewal_unique.sql` | Adds the unique `(ContractID, RenewalDate)` constraint. |
| Retraining module | `part4/python/retraining/module.py` | Hashes the BRFSS source, retrains when changed, validates, and publishes model artifacts. |
| Refresh orchestrator | `part4/python/run_rate_refresh.py` | Reloads staging after a source change and publishes a local rate version. |
| Source-revision simulation | `part4/python/simulate_source_revision.py` | Creates the fixed-seed simulated BRFSS coding revision used in the demonstration. |
| Retraining process diagram | `part4/diagrams/uc6_process.png` | Rendered retraining workflow with validation failure path. |
| Renewal process diagram | `part4/diagrams/uc7_process.png` | Rendered renewal workflow with rejection paths. |
| Deployed architecture diagram | `part4/diagrams/refarch_v3.png` | Rendered deployed reference architecture. |
| Future-state architecture diagram | `part4/diagrams/refarch_v3_future.png` | Rendered designed but not deployed components. |
| Screenshots | `part4/screenshots/` | Screenshots for the Part 4 demonstration sequence. |

The Mermaid sources for the four diagrams are in `part4/diagrams/src/`.

## Technology

- SQL Server 2022 dialect, deployed to Azure SQL Database and to local Docker.
- Azure Blob Storage for curated source files, model exports, metrics, and baseline metrics.
- Azure Functions for the Part 3 monthly rate refresh timer.
- Next.js with TypeScript for the application.
- The `mssql` driver for the main SQL Server access paths.
- Prisma for `GET /api/quote/options` and `POST /api/wellness/activity`.
- Python with scikit-learn for training, validation, staging, and rate publication.
- Oracle SQL Developer Data Modeler for the Part 1 and Part 2 models.

## Running it

The checked local environment used Docker 29.6.2, Node.js 20.19.5, and Python 3.14.6. SQL Server runs from the 2022 container image. The commands below are the documented local procedure. I did not retest a clean installation while preparing this README.

### Configuration

`part3/.env.example` lists the Azure variable names. Copy it to `part4/.env`, then add the local Docker variables required by the Part 4 application: `DATABASE_TARGET`, `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_SA_PASSWORD`, and `MSSQL_DATABASE`. Set `DATABASE_TARGET=local` for the local container. Set `DATABASE_TARGET=azure` with the `AZURE_SQL_*` values to select Azure SQL.

```sh
cp part3/.env.example part4/.env
```

`AZURE_STORAGE_CONNECTION_STRING` is required even for a local run. The retraining module reads the curated BRFSS source from Azure Blob Storage and writes its model output, metrics, and baseline metrics back there. Only the database target is local.

No credentials are tracked. `.env` and `.env.*` are ignored by the repository `.gitignore`.

### Schema deployment order

1. Apply `part2/schema_final.sql` for the base schema.
2. Apply `part2/bridge_schema.sql` for the bridge schema.
3. Follow `part3/sql/load/deploy_local.sql`. It applies the Part 3 `Contract` foreign keys, `part3/sql/physical/schema_amendments.sql`, and `part3/sql/physical/staging_amendments.sql`.
4. Load the data, then apply `part3/sql/physical/01_indexes.sql` and `part3/sql/physical/03_indexed_view.sql`.
5. Apply `part4/sql/01_data_source_state.sql`.
6. Apply `part4/sql/02_policy_renewal_unique.sql`.

`part3/sql/load/deploy_local.sql` is the documented local deployment script. It expects its referenced SQL files to be copied into `/tmp/dbsys-p3-deploy` inside the `dbsys-p3-mssql` container before `sqlcmd` runs it.

### Loading data

`part2/build_curated.py` creates the curated sample from the raw public-source files. The raw annual BRFSS archive is excluded from version control for size. Supply that public source before running the script.

The Part 4 staging loader accepts the curated BRFSS sample and loads the local staging tables.

```sh
cd part4
python3 -m venv .venv
.venv/bin/python -m pip install -r ../part3/requirements.txt
.venv/bin/python python/load_staging.py \
  --brfss-source data/curated/brfss_2024_life_risk_sample_50000.csv \
  --curated-dir ../part3/data/curated \
  --sql-load-file ../part3/sql/load/load_staging_local.sql \
  --env-file .env
```

### Starting the application

```sh
cd part4/web
npm install
npm run dev
```

Open `http://localhost:3000/quote`. The server-side database pool loads `part4/.env` from the application parent directory.

### Running a refresh

The Part 4 orchestrator runs against local Docker unless `--azure` is supplied.

```sh
cd part4
.venv/bin/python python/run_rate_refresh.py \
  --wonder-cohort-source-year 2023 \
  --loading-factor 1.5
```

The command checks the BRFSS source in Blob Storage, retrains only when its hash differs from the latest `DATA_SOURCE_STATE` row, reloads staging after a detected change, and publishes the next local rate book in one database transaction.

## The demonstration

1. I quoted the demonstration profile at $2,430.00 under rate version 1018.
2. I bound the application and created a contract pinned to rate version 1018.
3. I uploaded the fixed-seed simulated BRFSS coding revision.
4. I ran the refresh. It detected the changed hash, retrained the model, passed the validation gate, reloaded staging, and published rate version 1019.
5. I quoted the same profile again at $2,440.00 under rate version 1019.
6. I opened the bound contract and confirmed that its issued version remained 1018.
7. I renewed contract 60002. Its final renewal premium was $2,469.25 after a 15 percent wellness credit.

The screenshots are in `part4/screenshots/`. Section 8 of `part4/Feng_p4_report.docx` records the full sequence and evidence.

## Notes on scope

- The demonstration ran against local Docker SQL Server with Azure Blob Storage as the data lake. The solution deploys to Azure SQL Database, and `part3/docs/azure_deployment.md` carries the Azure evidence. Both targets use the same schema.
- The retraining module is not deployed to the Azure Function. The Function runs the Part 3 refresh on a monthly timer.
- Company data is synthetic and generated with a fixed seed. Health data comes from public CDC and SSA sources.
- The raw BRFSS annual file is excluded from version control for size. `part2/build_curated.py` produces the checked-in curated sample from it.
