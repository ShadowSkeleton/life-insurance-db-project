# Retraining Module Design

## Purpose

Part 3 built the path from curated datasets to a quoted premium. The scheduled
job reads the staging tables, rebuilds RISK_FACTOR from the model coefficients,
publishes a new RATE_VERSION, and records the work in DATA_REFRESH_RUN. That
path runs without me.

The step in front of it does not. The coefficients the job reads were produced
by opening a notebook and running it. When a new BRFSS release or a new WONDER
export lands in the lake, nothing retrains the model against it. The rate book
keeps being rebuilt from coefficients fitted to the previous data.

This module closes that gap. It detects that a source dataset has changed,
retrains the model on the changed data, and hands the new coefficients to the
refresh job that already exists.

## Placement

The module sits beside the Azure Function rather than inside it.

The Function keeps its monthly timer and its existing responsibility, which is
to turn coefficients into a rate book. Before it does that work it calls the
retraining module, which either reports that nothing changed or returns a new
set of coefficients.

I chose this split for the same reason I chose to read model output from blob
storage in Part 3 rather than bundle it into the deployment package. Training
and pricing change at different rates and for different reasons. Keeping them
separate means I can retrain without redeploying the Function, and the Function
stays small enough to start quickly. Putting scikit-learn inside the deployment
package would work but it couples two things that do not need to move together.

## Change detection

The Function fires monthly. The source datasets publish annually. Retraining on
every timer tick would refit the model to identical inputs eleven times a year,
which wastes the run and produces a stream of RATE_VERSION rows that record no
new information.

The module therefore decides what changed before it decides whether to train. It
computes a SHA-256 hash of the BRFSS curated sample in blob storage and compares
it against the hash recorded by the previous run. If the hash differs the file
changed and the model is refit. If it matches the module does nothing and the
refresh proceeds on the existing model.

I use content hashing rather than the blob last-modified timestamp because the
timestamp changes when a file is re-uploaded unmodified, and re-uploading is a
normal thing to do when a load fails partway. The hash answers the question the
specification actually asks, which is whether the source data changed, not
whether the file was touched.

## DATA_SOURCE_STATE

The recorded hashes live in a new table rather than in a file alongside the
model output.

    CREATE TABLE DATA_SOURCE_STATE (
      SourceStateID   INT IDENTITY(1,1) PRIMARY KEY,
      SourcePath      VARCHAR(255) NOT NULL,
      ContentHash     CHAR(64)     NOT NULL,
      ByteSize        BIGINT       NOT NULL,
      ObservedAt      DATETIME2    NOT NULL,
      ObservedByRunID INT          NOT NULL
        REFERENCES DATA_REFRESH_RUN(RunID)
    );

I considered keeping this state in blob storage next to the model output, which
would have cost no schema change. I chose the table for two reasons.

The first is lineage. The foreign key to DATA_REFRESH_RUN means a published rate
book can be traced back to the exact bytes the model was trained on. Joining
DATA_SOURCE_STATE to DATA_REFRESH_RUN to RATE_VERSION answers which source
version produced which prices, in one query. A file sitting in blob storage
cannot be joined to anything, so the same question would have to be answered by
reading files and matching them up by hand.

The second is transactional consistency. The hash record and the run record
commit together. A file-based record is a separate write, and a run that fails
after that write would leave a stored hash claiming a source was processed by a
run that never completed. The next run would then skip a file it should have
retrained on.

This is a Part 4 amendment rather than a Part 3 one, and the reason it appears
now is specific. Part 3 ran refreshes on a schedule and had nothing to compare
against. Part 4 runs them on change, and change requires prior state.

## Inputs

The module watches one file, the BRFSS 2024 curated sample in blob storage. This
is the file the model trains on, so a change to it is the case the specification
describes.

The other curated datasets serve different purposes. NHANES supplies the BMI
banding, and the WONDER and SSA exports validate the direction and ordering of
the fitted multipliers rather than supplying training rows. The refresh job reads
their staged representations from Azure SQL rather than reading the files. The
same hashing mechanism extends to them without change, and I note that as
available rather than demonstrated.

The module reads the previous hash from DATA_SOURCE_STATE. On a first run the
table holds no row for that path, and the module treats the file as changed.

## Outputs

When retraining occurs the module writes:

- A rebuilt training frame from the changed source
- A new predicted risk profile export to blob storage, at the path the Function
  already reads
- The evaluation metrics for the new fit, including AUC, calibration, and the
  subgroup breakdowns by sex and age band

The module does not write to DATA_SOURCE_STATE itself. It returns the observed
hash to the orchestrator, which inserts the row inside the refresh transaction.
The refresh publishes its writes as one self-contained transaction that an
external caller cannot join, so the insert has to happen from inside that same
unit of work rather than from the module.

It then returns the profile export location to the calling Function, which
proceeds with its existing work of rebuilding RISK_FACTOR and publishing a
RATE_VERSION.

When the source file has not changed the module writes nothing and returns the
location of the current profile export. The Function still runs, and the run is
still recorded, but the rate book it publishes is derived from the same model
as the previous one.

## Validation gate

A new fit is not automatically better than the one it replaces. The module
evaluates the retrained model before releasing it.

The gate is relative. It compares the new fit against the metrics recorded for
the fit currently in use, and it blocks publication only when the new model is
worse. It does not require the model to satisfy properties the current model
does not already satisfy.

I wrote it this way after an earlier version failed on its first run. That
version required the fitted mortality multipliers to rise monotonically with age
in the way the SSA period life table does. The Part 3 model does not satisfy
that property for either sex, which is recorded in its metrics and discussed as
a limitation. An absolute gate would therefore have blocked every retraining
attempt, including the first, which defeats the purpose of building the module
at all.

The three checks are:

- The AUC must not fall more than 0.02 below the recorded baseline
- The direction of the diabetes effect must still agree with the WONDER cohorts
- The count of SSA ordering violations must not increase above the baseline

The baseline metrics are stored in blob storage alongside the profile export, so
each run compares against the fit that produced the rates currently in force.

If a check fails the module keeps the previous profile export, records the
failure on the run, and does not publish. The rate book continues to price from
the model already in use.

This is the mechanism that limits how much the automated pipeline can move
prices without review. Retraining is automatic. Publishing a model that performs
worse than its predecessor is not.

## Failure handling

The refresh job already runs its database writes inside one transaction. The
connection is opened with autocommit disabled, commits only after every write
and validation has passed, and rolls back on any exception. RISK_FACTOR,
RATE_VERSION, and RATE therefore move together or not at all, and a failed run
leaves the previous rate book active.

The retraining module inserts its DATA_SOURCE_STATE row inside that same
transaction. This matters because the row is what tells the next run that a file
has already been trained on. If the row committed separately and the refresh
then failed, the next run would skip a file it should have retrained on, and the
change would be lost silently.

Writes to blob storage sit outside the transaction and cannot be rolled back. A
run that writes a new profile export and then fails in the database leaves that
export in place with no DATA_SOURCE_STATE row referencing it. The next run sees
the source hash as still unmatched, retrains again, and overwrites it. Repeating
the work is the correct outcome here, because the alternative is treating an
uncommitted run as finished.

DATA_REFRESH_RUN carries a Status column with a failed value, and the refresh
job already writes a failure row with the stage recorded in Notes.

## Sequence

1. The timer fires and the orchestrator begins a refresh.
2. The module hashes the source file in the lake and compares it against the
   latest DATA_SOURCE_STATE row for that path.
3. If the hash matches, the module returns the current profile export location
   and the run proceeds without retraining.
4. If the hash differs, the module loads the changed source, rebuilds the
   training frame, and refits the model.
5. The module evaluates the new fit against the validation gate.
6. If the gate passes, the module writes the profile export and metrics to blob
   and returns the new location together with the observed hash.
7. If the gate fails, the module returns the previous location and records the
   failure on the run.
8. The orchestrator opens the publication transaction, inserts the
   DATA_REFRESH_RUN row with status running, inserts the DATA_SOURCE_STATE row
   against that RunID, and rebuilds RISK_FACTOR from the returned profile
   export, tagging rows with the RunID.
9. The orchestrator supersedes the active RATE_VERSION, publishes the
   replacement, and inserts the RATE rows.
10. The transaction commits and the run is marked complete with the new
    RateVersionID recorded.

## Effect on existing policies

Nothing in this module changes an issued policy. Contract carries
IssuedRateVersionID, which fixes each policy to the rate book in effect when it
was issued. A new RATE_VERSION is visible to new applicants and to renewals. It
is not visible to a policy already in force.

This is the behavior the professor confirmed by email, and the retraining module
does not alter it. Retraining changes which coefficients produce the next rate
book. It does not reach back into contracts.
