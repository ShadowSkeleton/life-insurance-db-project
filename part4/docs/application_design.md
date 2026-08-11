# Application design

## 1. Scope

Part 3 documented five business use cases and drew a process model for each. It
also drew the asynchronous boundary that separates the customer paths from the
repricing job. This document covers what those did not, which is the design of
the application itself. It describes the layers, the connectivity, the route
inventory, the transaction boundaries, and the point where the retraining module
attaches to the workflow.

The application is a Next.js program written in TypeScript. It runs the quote,
bind, wellness, renewal, and administrative paths against SQL Server. Part 3
built it as a demonstration and did not require it. Part 4 requires it, so this
document treats it as a deliverable rather than a convenience.

## 2. Layers

There are four layers and one process that sits beside them.

The browser holds the pages. These are React components under `app/`, and they
hold no database logic. A page renders state and calls a route.

The route layer under `app/api/` holds the workflow logic. A route validates its
input, decides what the operation means, opens a transaction where one is
needed, and returns a result the page can render. This is where a quote becomes
an application row and a renewal becomes a POLICY_RENEWAL row.

The query layer in `lib/queries.ts` holds the SQL. Keeping statements here
rather than inline in routes means the same statement can be reused. The quote
path and the renewal path use the same active-rate lookup, and the wellness page
and the renewal route use the same wellness credit query. If the credit rule
changes, it changes in one place.

The database is SQL Server, either the Azure instance or the local container.
Both hold the same schema.

Beside these sits the Python pipeline. It is not part of the web application. It
performs change detection, retraining, the validation gate, the staging reload,
and the rate refresh. The application invokes it and reports its result. The
reason for keeping it separate is in section 6.

## 3. Connectivity

Database access is through the `mssql` package and happens only on the server. No
page holds a connection string and no browser code touches the database.

`lib/db.ts` creates one connection pool and stores it on the global object, so
route modules and development server reloads share a single pool rather than
opening one each. The pool allows a maximum of ten connections, a minimum of
zero, and a thirty second idle timeout. The minimum of zero matters on Azure,
because the serverless tier auto pauses when idle and an idle open connection
prevents that from happening.

Configuration is read from the environment at startup. The same code selects
Azure when `AZURE_SQL_SERVER` is present and the local container otherwise, so
switching between them requires changing environment values rather than editing
code. A template file records which variables are required and carries no
values.

## 4. Route inventory

| Route | Reads | Writes |
|---|---|---|
| `GET /api/quote/options` | Product | none |
| `POST /api/quote` | Customer, RATE_VERSION, RISK_FACTOR, RATE, APPLICATION | APPLICATION |
| `POST /api/bind` | APPLICATION, Contract | Contract, APPLICATION |
| `GET /api/wellness` | Contract, APPLICATION, WELLNESS_ENROLLMENT, WELLNESS_PROGRAM, RATE_VERSION, RISK_FACTOR, RATE, RISK_IMPROVEMENT, vWellnessActivityEnrollmentYear | none |
| `POST /api/wellness/enrollment` | WELLNESS_ENROLLMENT, WELLNESS_PROGRAM | WELLNESS_ENROLLMENT |
| `POST /api/wellness/activity` | none | WELLNESS_ACTIVITY |
| `POST /api/wellness/screening` | WELLNESS_ENROLLMENT | RISK_IMPROVEMENT |
| `POST /api/renew` | Contract, APPLICATION, RATE_VERSION, RISK_FACTOR, RATE, RISK_IMPROVEMENT, POLICY_RENEWAL | POLICY_RENEWAL |
| `POST /api/reprice` | invokes the pipeline | DATA_REFRESH_RUN, DATA_SOURCE_STATE, RISK_FACTOR, RATE_VERSION, RATE |
| `GET /api/reprice/history` | RATE_VERSION, Contract, DATA_REFRESH_RUN, DATA_SOURCE_STATE | none |
| `GET /api/analytics` | RATE_VERSION, Contract, STG_BRFSS, STG_MORTALITY, DATA_REFRESH_RUN, WELLNESS_ENROLLMENT, vWellnessActivityEnrollmentYear | none |

Only one route writes rate data, and it does so by invoking the pipeline rather
than by writing rows itself. No route writes to Contract except bind. Nothing in
the repricing path can reach Contract at all, which is how the second required
mechanism is enforced.

## 5. The quote and renewal paths

Both paths answer the same question, which is what this profile costs. They
differ in which rate version they ask.

The quote path derives an age band and a BMI band from what the applicant
entered, then joins RATE_VERSION to RISK_FACTOR to RATE where the version status
is active and the profile columns match. The premium is the base rate times the
face amount divided by one thousand. The quoted rate version is stored on the
APPLICATION row, and on bind it is copied to `Contract.IssuedRateVersionID`.
That column is what pins the policy.

The renewal path reads the contract and its joined APPLICATION for the same
profile columns, so no one re-enters a medical profile at renewal. It then runs
the same lookup against the current active version rather than the issued one.
This is the whole point of the mechanism. A renewal sees today's rates.

The wellness credit is then applied. The credit is the mean of positive
`RISK_IMPROVEMENT.ImprovementPct` values measured strictly before the renewal
date, rounded to two decimals and capped at fifteen percent. A contract with no
qualifying measurement receives zero. The cap is applied in SQL rather than in
the route, so any caller gets the same bounded value.

The result is written as a POLICY_RENEWAL row carrying the contract, the renewal
date, the new rate version, the discount percentage, and the final premium.
Nothing on the Contract row changes.

That last decision is worth stating. I considered updating
`Contract.ModalPremium` to the renewed amount so the contract row would show
what the customer currently pays. I did not, because the wellness screen labels
that column as the issued premium and several queries read it as an issue-time
value. Updating it would make those readings wrong. The contract stays the
issue-time record and the renewal carries the renewal outcome. The current
effective premium is a join rather than a column.

## 6. Where the pipeline attaches

The pipeline runs as a separate Python process. `POST /api/reprice` spawns it,
waits for it to exit, and reads a structured result line from its output.

I kept it separate for the same reason I read the model export from blob storage
in Part 3 rather than bundling it into the Function package. Training and
pricing change for different reasons and on different schedules. Bundling
scikit-learn into the web application would couple a deployment of one to a
deployment of the other, and would put a multi-minute training run inside a
request.

The route holds a module level flag that rejects a second refresh while one is
running. This is a single process guard and would not survive multiple
instances. For a single-instance demonstration it is the right size of solution,
and the database transaction is what actually protects correctness.

The pipeline reports one of three outcomes and the route surfaces all three
rather than collapsing them into success or failure. The source may not have
changed, in which case no retraining happened and the refresh republished from
the existing model. The source may have changed and the retrained model passed
the validation gate, in which case the new model produced the new rates. Or the
source may have changed and the retrained model failed the gate, in which case
fitting happened but nothing was published and the previous model still prices.

The third case is the one that would be easy to report wrongly. The refresh
succeeded and a rate version was published, but not from the new model. An
administrator needs to see that distinction, so the response carries the gate
comparisons and their numeric values rather than a pass or fail flag.

## 7. Transaction boundaries

Three operations are transactional and one deliberately is not.

The rate refresh writes DATA_REFRESH_RUN, DATA_SOURCE_STATE, RISK_FACTOR,
RATE_VERSION, and RATE inside one transaction. It commits after every write and
validation passes and rolls back on any exception. This is inherited from Part 3
and Part 4 added the DATA_SOURCE_STATE insert to it. That insert has to be
inside the transaction rather than beside it. The row is what tells the next run
that a source file has already been trained on, so a row committed by a run that
then failed would cause the next run to skip a changed file and lose the change
silently.

The renewal writes one row and checks for an existing renewal on the same
contract and date first. I first wrote this at serializable isolation so the
check and the insert could not interleave with a concurrent request. After
adding a unique constraint on `(ContractID, RenewalDate)` the database enforces
that directly, so the route runs at read committed and the constraint is what
prevents a duplicate. Enforcing it in the schema is cheaper than holding range
locks on a ninety thousand row table.

The bind operation writes Contract and updates APPLICATION together, since an
application marked bound with no contract would be a lie.

The staging reload is not transactional and cannot be. It truncates and bulk
loads through a separate session, so it commits on its own. If the rate
publication then fails, the reloaded staging population stays while the rate
transaction rolls back. The next run finds no committed DATA_SOURCE_STATE row
for the current hash, treats the source as unprocessed, and repeats the work.
Repeating is the correct outcome here. The alternative is treating an
uncommitted run as finished.

## 8. Rejection paths

A route that cannot complete rejects with a message rather than writing a
partial row.

The renewal route rejects when the contract has no APPLICATION, when no rate
version is active, when no RATE matches the profile under the current version,
and when a renewal already exists for that contract and date. Each of these is a
real condition rather than a defensive check. A contract without an application
predates the Part 3 amendment. No matching rate means the profile bands moved
between versions.

The reprice route rejects an unsupported cohort year or a non positive loading
factor before spawning anything, and reports a distinct message when the process
cannot start at all, since that means a broken Python environment rather than a
failed refresh.

## 9. What the application does not do

It does not train the model. It does not write rate data directly. It does not
modify a contract after issue. It holds no scheduling logic, because the monthly
timer lives in the Azure Function.

Listing these matters as much as listing what it does. The application is the
part a customer touches, and the design keeps the pricing machinery on the other
side of a boundary that only the administrative route crosses.
