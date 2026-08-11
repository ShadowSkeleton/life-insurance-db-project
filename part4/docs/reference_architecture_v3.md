# Reference architecture version 3

Version 2 described what was deployed at the end of Part 3 and separated it from
what was designed but not built. Version 3 states the architecture as a whole.
It gives the principles the design answers to, the framework that organizes it,
the methods used to plan, deliver, and operate it, and the governance that keeps
it honest. It also covers the retraining loop and the source state table, which
did not exist when version 2 was written.

## Foundational principles

These are the commitments the rest of the architecture serves. Each one was
established earlier in the project and each one is enforced somewhere in the
schema or the code rather than only in documentation.

A rate revision never touches an in-force policy. The repricing path writes
rate data and has no write edge to Contract. An issued policy keeps its
IssuedRateVersionID after a new version is published, so its premium does not
move. This is the second mechanism the professor required and it is enforced by
the absence of a code path rather than by a rule someone has to remember.

Every published number traces back to the data that produced it. Staging
rows carry their source file. RISK_FACTOR rows carry the run that derived them.
RATE_VERSION rows carry the run that created them. DATA_SOURCE_STATE carries the
hash of the source file the run observed. A published premium can be traced to
the bytes it came from by following foreign keys.

Sources are separated by the role they can support. SSA supplies an absolute
mortality baseline by age band and sex. CDC WONDER supplies the diagnosed
diabetes relative effect. BRFSS supplies differentiation within the disclosed
non diabetic class. Keeping these separate prevents a diabetes association
coefficient from being used as an all cause mortality weight.

A disclosed fact is authoritative and the model refines rather than
overrides. An applicant who discloses diabetes receives the WONDER derived
effect. The model differentiates residual risk only among applicants who
disclose no diabetes. It never contradicts the answer the applicant gave.

Limitations stay visible rather than being corrected away. Where the derived
relative risks came out lower than expected they were retained as observed
rather than adjusted with an invented uplift. Missing BMI was left unimputed
rather than filled by an unvalidated model. The SSA ordering violations are
recorded in the model metrics rather than smoothed. A limitation that is
documented can be reasoned about. One that has been quietly adjusted cannot.

Automation proposes and evidence disposes. The pipeline retrains without
human involvement, but it publishes only when the retrained model passes the
validation gate. Failed sources, a model that performs worse than its
predecessor, and failed publication all leave the existing rate book in place.

## Organizing framework

The architecture is organized along two axes. The first is the DIKW layering,
which describes how a public health record becomes a price. The second is the
synchronous and asynchronous boundary, which describes what may run while a
customer is waiting and what may not.

The DIKW axis is visible in the tables rather than hidden in scripts. Source
grain records live in STG_BRFSS_RECORD. Conditional summaries live in STG_BRFSS
and STG_MORTALITY. Derived multipliers live in RISK_FACTOR. Published prices
live in RATE_VERSION and RATE. Each transition is a table rather than a
transformation inside application code, which is what makes the pipeline
auditable.

The boundary axis separates the quote and renewal paths, which run while a
person waits, from the refresh path, which runs on a schedule. The refresh reads
staging and the model export and writes rate data. It does not write Contract.
A rate revision therefore never interrupts a live application and never silently
reprices a policy in force.

Version 3 adds a third element inside the asynchronous side. The refresh no
longer begins with a rebuild. It begins with a comparison. The retraining module
hashes the source file, compares it against DATA_SOURCE_STATE, and retrains only
when the bytes have changed. The rate refresh that follows is unchanged from
Part 3. The addition is a gate in front of it.

## The four domains

### Business

The company sells life insurance to individual applicants. An applicant supplies
a medical profile and receives a quote. If they bind, the contract is pinned to
the rate version active at that moment. At renewal the policy is repriced
against the current version, offset by measured improvement from the wellness
program.

Three business rules drive the architecture, and they are the three the
professor confirmed. Pricing is revised asynchronously from external datasets.
Existing policyholders are unaffected by a revision while new applicants receive
current rates. Renewals are repriced against new rates with wellness offsets.

The wellness loopback is the part that connects the business model back to the
data. Wellness activity records participation, but participation alone does not
change a premium. The renewal credit is the mean of positive measured
improvement dated before renewal, capped at fifteen percent. The program
therefore measures improvement in the same variables the company prices on
rather than rewarding attendance.

### Application

A Next.js application provides the customer and administrative paths. Quote and
bind write APPLICATION and Contract. The wellness screens write enrollment,
activity, and measured improvement. The renewal action writes POLICY_RENEWAL
against the current active rate version. The administrative screens expose the
refresh history, the source state lineage, and the validation gate results.

All database access is server side through a shared connection pool. The
application never holds credentials in source. Configuration is read from the
environment, and the same code selects Azure SQL or the local instance depending
on which settings are present.

The retraining module sits beside the application rather than inside it. The
administrative repricing action invokes an orchestrator that performs change
detection, conditional retraining, the validation gate, the staging reload, and
the rate refresh. The application surfaces the outcome. It does not implement
the pipeline.

### DIKW

| Level | Component | Meaning here |
|---|---|---|
| Data | Curated lake files, STG_BRFSS_RECORD, DATA_SOURCE_STATE | Source grain records, retained source files, and the observed hash of each file version |
| Information | STG_BRFSS and STG_MORTALITY | Conditional prevalence and normalized mortality inputs, each carrying its source |
| Knowledge | Model export and RISK_FACTOR | Residual diabetes risk and the derived mortality multipliers, each tied to the run that produced it |
| Wisdom | RATE_VERSION, RATE, quoted premiums, renewal offsets | Published pricing decisions applied without disturbing policies already in force |

Version 3 places DATA_SOURCE_STATE at the Data level deliberately. It is not a
summary or a derivation. It is a record of what the source was at a point in
time, which is what makes every level above it explicable.

### Infrastructure

Azure Blob Storage holds the raw and curated lake files and the model export.
Azure SQL Database holds the operational schema, the staging tables, and the
published rate books. An Azure Function runs the refresh on a monthly timer,
which matches the annual publication cadence of the source datasets without
requiring anyone to remember to run it.

A local SQL Server instance in Docker holds the same schema and is used for
iteration and measurement. Running both means physical design work can be
measured without consuming cloud quota, and the deployed environment can be
verified separately.

Synapse serverless, Event Hubs, and Stream Analytics remain designed rather than
deployed. Synapse is not deployed because the storage account has hierarchical
namespace disabled. The streaming components are future state for a continuous
wellness feed. Naming them as unbuilt is part of the architecture rather than an
omission from it.

## Methods

### Plan

Business use cases come first, then process models, then schema. The five use
cases map onto the three required mechanisms, and each process model states its
postconditions, including the ones that must not happen. The postcondition that
publishing a rate version does not modify a Contract is what the asynchronous
boundary diagram exists to make visible.

Schema changes are amendments with stated reasons rather than edits. The
APPLICATION table was added in Part 3 because the pricing pipeline could not
match a contract to a rate without a persisted applicant profile.
DATA_SOURCE_STATE was added in Part 4 because change detection requires prior
state and Part 3 had none to compare against.

### Deliver

Physical design was built in measured increments rather than applied at once,
with logical reads captured after each increment. Logical reads rather than
elapsed time because emulation on this hardware makes wall clock timing
unreliable, and because logical reads are the quantity the design actually
changes.

The same discipline applies to Part 4. The effective premium query was measured
against a forced table scan before deciding whether a new index was warranted.
It was not, because the existing unique key on POLICY_RENEWAL supports the
descending order through a backward seek. Five logical reads against seven
hundred and twenty eight, without adding an index.

Earlier parts are frozen once submitted. Where Part 4 needed to change a Part 3
script, the script was copied into Part 4 and the copy modified. This keeps each
submission a fixed artifact and makes the difference between parts inspectable.

### Operate

The refresh runs monthly on a timer. Each run records its type, its status, the
datasets it read, and the rate version it produced. A run that retrains also
records the hash of the source it trained on.

Publication is versioned rather than replacing a live rate book. A new version
closes the previous one and leaves existing contracts pinned to theirs. A failed
run rolls back, and the previous version remains active.

Retraining is triggered by content change rather than by schedule. A monthly
timer against annually published sources would otherwise refit an unchanged
model eleven times a year and produce a stream of rate versions recording no new
information.

## Governance

### Data quality management

Quality is enforced at three points.

At load, the BRFSS recodes normalize survey codes into modelled values, the
staging loader retains all fifty thousand curated records at source grain, and
validation scripts assert row counts, date ordering, and referential integrity.

At training, the model is validated against external references rather than
against itself. The SSA period life table checks ordering. The CDC WONDER
cohorts check the direction of the diabetes effect. Calibration and subgroup
performance are computed and recorded.

At publication, the validation gate compares the retrained model against the fit
currently in use. The AUC must not fall more than 0.02 below the recorded
baseline. The direction of the diabetes effect must still agree with WONDER. The
count of SSA ordering violations must not increase. A model that fails any of
these is not published and the previous model continues to price.

The gate is relative rather than absolute for a reason worth recording. An
earlier version required the fitted multipliers to rise monotonically with age
as the SSA table does. The model does not satisfy that property for either sex,
which is documented in its metrics. An absolute gate would have blocked every
retraining attempt including the first. A gate that requires a property the
system has never had is not a quality control. It is an obstruction.

### Prevention of data loss and leakage

No credential appears in source. Connection settings are read from the
environment at runtime, and a template file records which variables are required
without carrying any values. Before the repository was first published, every
file was scanned for credential shaped content and each match was confirmed to
be an environment lookup rather than a literal.

The Blob credential in Azure uses a shared access signature with a bounded
expiration, which must be rotated. Recording that as a live obligation rather
than a completed step is the honest position.

The company side data is synthetic rather than drawn from real policyholders.
The external health data is public and aggregated with no individual records.
The system therefore holds no identifiable personal health information, which
limits the consequences of any leak rather than relying only on preventing one.

Large raw source files are excluded from version control and fetched by script.
This keeps the repository usable and avoids redistributing federal datasets that
are already published elsewhere.

### Management of the data lifecycle

Raw and curated files are kept separately in the lake. Raw folders hold the
original downloads untouched, one per source. The curated folder holds cleaned
extracts containing only the columns the project uses. Keeping both means the
path from a curated number back to its original file is never lost.

Retention differs by role. Staging rows are replaced on each refresh and do not
need to be kept, because the curated files are the durable copy and each staging
row carries a reference to its source. Rate versions are the opposite case and
must be kept indefinitely, because a policy issued years ago is still pinned to
the version it was priced under, and removing that version would make its
premium impossible to explain.

DATA_SOURCE_STATE extends this to the source files themselves. Each row records
the hash, size, and observation time of a source file version, and the run that
observed it. The lineage from a published premium to the exact bytes behind it
is a join rather than a manual reconstruction.

Not every available file enters the pipeline. The NIDDK material remains a
published reference and is cited rather than loaded. Distinguishing pipeline
input from supporting citation is what keeps the lake from becoming a data
swamp as more files arrive.

### Bias, fairness, accountability, and transparency

The model is a diabetes risk estimator, not a mortality model, and the
architecture states that boundary rather than leaving it implied. It
differentiates residual risk within the disclosed non diabetic class. It does
not set the diagnosed diabetes multiplier and it does not supply mortality
weights for smoking or BMI. The K means clustering is descriptive and is used
for product presentation and outreach, not as a pricing class.

Subgroup performance is measured rather than assumed. Female AUC is 0.771 and
male AUC is 0.777, which is close enough that neither sex is served materially
worse by the model. Age band AUC ranges from 0.803 at ages 35 to 39 down to
0.652 at ages 80 to 99. The oldest band is worst, and the reason is structural:
it compresses six five year ages into one group, making it both substantively
and statistically harder to discriminate. That band is where the model's output
deserves the least weight.

The rating variables carry different risks. Age, smoking, diabetes status, and
BMI are candidate rating inputs where the company can show a sound actuarial
basis and comply with state law and filing rules. Sex distinct rating is
standard practice in United States individual life insurance and is reflected in
the SSA baseline the pricing uses, though Montana requires unisex rating and
employer sponsored group coverage is governed differently. The European Union
prohibits its use in insurance pricing entirely. BMI carries a separate concern.
It can have different validity across populations and can act as a proxy for
unobserved social and health conditions, which means it may encode more than the
biometric it appears to measure.

BMI is also missing for 4,631 BRFSS records. Missing values can correlate with
refusal to report height or weight, so the estimated BMI effect may be biased
toward zero. No imputation was applied, because a complete observed measurement
is a transparent baseline and an unvalidated imputation model would hide the
problem rather than solve it. The need for later imputation and a missingness
indicator comparison is recorded.

Limiting the decision power of the system is the validation gate. The pipeline
can retrain itself without anyone watching. It cannot publish a model that
performs worse than the one already pricing policies. Retraining is automatic.
Moving prices on a degraded model is not.

Accountability rests on the lineage. Because rates are versioned, because each
version records the run that produced it, because each run records the source
hash it observed, and because each contract is pinned to the version it was
issued under, the company can explain why any given policy was priced the way it
was. That explanation is a query rather than a reconstruction, which is the
difference between a system that can be audited and one that merely claims to
be.
