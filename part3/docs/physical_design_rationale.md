# Jingrui Feng (jf4446) - database systems project part 3 - measured index and partition rationale

# Physical database design rationale

## Measurement methodology

All figures below are from the local Docker SQL Server captures in
`outputs/baseline/` and `outputs/increment1/` through `outputs/increment3/`.
Logical reads and actual execution-plan shape are the reported measures. Every
per-query figure in this document uses the **all tables touched** convention:
the logical reads of every user table reported by `SET STATISTICS IO` for that
query are summed. The original 996-page Q1 figure was the ContractParty main
table alone; its reconciled all-tables figure is 999 after including Contract's
three reads. The engine runs under Rosetta 2 emulation on Apple Silicon, so elapsed time includes
instruction-translation overhead and is not comparable with Azure SQL Database
or native SQL Server hardware. Each query was executed twice without clearing
the buffer cache, with the first execution discarded.

## 1. Why a particular column needs an index

The strongest response-time evidence is `ContractParty.Customer_CustomerID`.
Q1 read 999 pages across ContractParty and Contract at baseline, including a
996-page clustered scan of ContractParty for one customer. The nonclustered
customer-key index reduced the complete query to five pages, a 99.50 percent
reduction. `Invoice.BillingAccount_BillingAccountID` likewise changed Q2b from
2,603 pages to 33 pages in Increment 1 because the direct billing-account
lookup became a seek followed by ten key lookups.

The wellness index uses `(EnrollmentID, ActivityDate)` and includes
`VerifiedFlag`. The included flag makes Q4's qualifying-count aggregation
covering while keeping the high-value enrollment/date navigation columns in the
key. Q4 dropped from 4,562 pages to seven in Increment 1. The narrower path
also reduced Q5 from 4,562 to 2,794 pages before partitioning.

| Query | Baseline reads | Increment 1 reads | Change | Increment 1 main access |
|---|---:|---:|---:|---|
| Q1 | 999 | 5 | -99.50% | ContractParty Index Seek |
| Q2 | 4,649 | 1,309 | -71.84% | ContractParty index scan; Invoice seek |
| Q2b | 2,603 | 33 | -98.73% | Invoice clustered key lookup after FK seek |
| Q4 | 4,562 | 7 | -99.85% | WELLNESS_ACTIVITY Index Seek |
| Q5 | 4,562 | 2,794 | -38.75% | WELLNESS_ACTIVITY Index Scan |
| Q8 | 2,848 | 176 | -93.82% | Contract ActivityStatus Index Seek |

The ActivityStatus count workload is retained separately from the retrieval
workload. The covered count pair later confirms that the narrow status index is
valuable even for a common value; the retrieval pair supplies the required
key-lookup crossover evidence under the same predicates.

## 2. Why a large table should be partitioned

`WELLNESS_ACTIVITY` holds one million rows across the six yearly partition
slices, while the renewal workload filters 2025. Increment 2 kept ActivityID's
uniqueness by moving the primary key to a nonclustered constraint and clustered
the table on `(ActivityDate, ActivityID)` aligned to the yearly scheme. Q4 and
Q5 plans each accessed partition 5 only, one of six, for their 2025 predicates.
Q5 consequently fell from 2,794 Increment-1 pages to 423 Increment-2 pages,
an 84.86 percent reduction attributable to partitioning and alignment. Q4
remained at seven pages because its existing selective enrollment/date seek was
already inexpensive, although the plan still proves one-partition elimination.

Invoice was similarly clustered on `(RunDate, InvoiceID)` after preserving its
nonclustered unique InvoiceID primary key. Q2 and Q2b have no RunDate predicate,
so their Invoice access paths legitimately span all six index partitions and do
not receive partition-elimination benefit. Q2b rose from 33 to 41 pages after
the restructure, a 24.24 percent Increment-2 increase. Q7 remains at 728 pages
and touches no partitioned table because the authorized partition targets were
WELLNESS_ACTIVITY and Invoice, not POLICY_RENEWAL.

## 3. Which queries the design is intended to improve

| Query | Baseline reads | Final reads | Final change | Primary technique responsible |
|---|---:|---:|---:|---|
| Q1 | 999 | 5 | -99.50% | ContractParty customer index |
| Q2 | 4,649 | 1,327 | -71.46% | ContractParty and Invoice indexes |
| Q2b | 2,603 | 41 | -98.42% | Invoice billing-account index |
| Q3 | 2 | 2 | 0.00% | Deliberately no new index |
| Q4 | 4,562 | 7 | -99.85% | Partition-aligned base index; 2 with explicit view NOEXPAND |
| Q5 | 4,562 | 423 | -90.73% | One-partition base-table index; 34 with explicit view NOEXPAND |
| Q6 | 1,424 | 1,424 | 0.00% | Scan remained preferable |
| Q7 | 728 | 728 | 0.00% | Scan remained preferable |
| Q8a count: Lapsed | 1,424 | 29 | -97.96% | Covered Contract status index |
| Q8b count: Active | 1,424 | 147 | -89.68% | Covered Contract status index |
| Q8a retrieval: Lapsed | 1,424 | 1,424 | 0.00% | Non-covering index declined; clustered scan |
| Q8b retrieval: Active | 1,424 | 1,424 | 0.00% | Non-covering index declined; clustered scan |
| Q9 | 1,240 | 1,240 | 0.00% | Deliberately no staging index |

The daily indexed view was rebuilt as `vWellnessActivityEnrollmentYear`, with
32,863 current enrollment-year rows and a clustered key of `(ActivityYear,
EnrollmentID)`. The prior daily view held 245,170 rows and required a 913-read
scan for Q5. The yearly view is not automatically matched because Q4 and Q5
express a date range while the view groups by year, and the optimizer cannot
prove that the two expressions are equivalent. Their default plans therefore
correctly remain the partitioned base-table paths at seven and 423 reads.

When the renewal-credit question is aligned to the materialized annual grain,
the explicit view query with `NOEXPAND` uses a clustered index seek and reads
two pages for the single-enrollment case and 34 pages for the all-enrollment
case, compared with seven and 423 pages on the partitioned base table. This is
the materialization finding: selective materialization required aligning the
query to the materialized grain, not merely adding storage. It changes how the
question is asked, which is a cost distinct from the view's storage cost.
`NOEXPAND` is supported on all SQL Server editions and Azure SQL Database,
whereas automatic indexed-view matching is edition dependent. Requiring the
hint for this specialized renewal-credit query therefore makes the design more
portable, not less.

## 4. What tradeoffs the design introduces

The storage baseline was 140,000 KB. Increment 1 added the six indexes and
raised total allocated storage to 173,760 KB, a 24.11 percent increase. The
partitioning restructure and six local data files raised total storage to
214,080 KB, a further 23.20 percent increase from Increment 1. The corrected
annual indexed view materializes 32,863 current rows and adds only 1,032 KB, producing
a final 215,112 KB total, 53.65 percent above baseline. The preceding daily-view
experiment had a 58 percent aggregate increase; under either measured total,
the annual view's 1,032 KB is trivially cheap relative to the indexes and
partitioning structure.

FILLFACTOR 80 is used for indexes on continuing Contract, Invoice,
WELLNESS_ACTIVITY, and POLICY_RENEWAL insert paths. It trades storage density
for reserved page space and fewer future page splits. The load-once
ContractParty customer index uses FILLFACTOR 100. Staging indexes were not
added, so the bulk-load staging process retains dense load-once primary-key
storage rather than paying maintenance for indexes that the full-scan refresh
does not seek.

No RATE_VERSION index was created because Q3 scans only two pages of the current
eleven-row dimension. No STG_* indexes were created because Q9 remains a full-refresh
aggregation and stayed at 1,240 pages; an index would add bulk-write and
maintenance cost without a selective access path. SQL Server has no clustering
construct separate from the clustered index already used for physical row order;
the partition-aligned clustered indexes are therefore the relevant clustering
choice.

Q6, Q7, and Q8 show the key tradeoff directly. Q6 returns 12,448 of 60,000
contracts, or 20.7 percent, and Q7 returns 7,548 of 90,000 renewals, or 8.4
percent. Their purpose-built non-covering indexes remain available, but the
optimizer correctly chooses clustered scans because a seek followed by thousands
of lookups costs more than scanning 1,424 Contract pages or 728 POLICY_RENEWAL
pages. The covered Q8 counts behave differently: Lapsed, 8,506 of 60,000 or
14.2 percent, uses 29 status-index pages, while Active, 46,679 of 60,000 or
77.8 percent, uses 147 index pages. Once Q8 retrieves EffectiveDate and
ModalPremium, neither value is covered and both predicates use a 1,424-page
clustered scan.

The optional crossover experiment isolated that behavior with a temporary,
non-covering `EffectiveDate` index on Contract. The index was removed after
measurement, so it is not part of the final design.

| Approximate target | Rows returned | Selectivity | Logical reads | Plan operator |
|---:|---:|---:|---:|---|
| 50 | 52 | 0.087% | 170 | Index seek plus key lookup |
| 250 | 251 | 0.418% | 779 | Index seek plus key lookup |
| 1,000 | 1,010 | 1.683% | 1,424 | Clustered index scan |
| 3,000 | 3,002 | 5.003% | 1,424 | Clustered index scan |
| 8,500 | 8,504 | 14.173% | 1,424 | Clustered index scan |

The crossover is between 0.418 and 1.683 percent, much lower than intuition
based on row counts alone. Each key lookup is random I/O that can cost several
pages, so a few thousand lookups outweigh reading the table sequentially. The
choice is therefore driven by row width, clustering, and lookup cost as well as
selectivity.

## 5. How the design supports expected workflows

The customer and billing-account indexes support interactive service and billing
history requests. The customer path reduces Q1 to five logical reads, and the
account-level billing path reduces Q2b to 41 final pages while respecting the
declared BillingAccount grain rather than inventing a policy-invoice link. The
wellness index and yearly partitions support the default renewal-credit work:
the annual all-enrollment calculation reads 423 pages and the per-enrollment
calculation reads seven. A dedicated renewal-credit query can use the annual
view with `NOEXPAND` for 34 and two pages respectively, but that dependency is
explicit because the optimizer does not match the view automatically. The rate
version and renewal indexes are retained as measured candidates even though the
current synthetic predicate volumes still favor scans; that result prevents a
claim of benefit not supported by the current book of business.

The index definitions, partition function, partition schemes, primary-key
restructure, and indexed view all transfer to Azure SQL Database. The local
six-filegroup placement does not: Azure SQL single databases expose PRIMARY, so
the Azure deployment script maps all six logical partitions to PRIMARY. The
separate [Azure-portable deployment script](../sql/physical/deploy_physical_azure.sql)
is intentionally not executed in this local measurement task.
