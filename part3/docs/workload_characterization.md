# Jingrui Feng (jf4446) - database systems project part 3 - workload characterization

# Physical-design workload characterization

The local baseline was captured before any discretionary index, partition
function, partition scheme, or indexed view was created. Baseline therefore
means the clustered indexes that back primary keys and the nonclustered indexes
that back unique constraints only. The catalog contained zero discretionary
indexes at capture time.

Response time governs representative-facing lookups such as Q1 through Q3 and
the paired invoice-history requests Q2 and Q2b. Space utilization governs the
choice to add an index or materialized structure only when its read reduction
justifies its stored pages and write maintenance. Transaction throughput governs
the renewal, wellness, and external-data refresh work because those operations
process many rows in a scheduled interval rather than serving a single user.

| Query | Business use case | Profile and expected frequency | Tables touched | Baseline access evidence |
|---|---|---|---|---|
| Q1 | Retrieve a customer's policies | Transactional; per service inquiry | ContractParty, Contract | ContractParty clustered-index scan, 996 logical reads; Contract primary-key seek, 3 reads |
| Q2 | Retrieve policy invoice history through account billing | Transactional; per policy inquiry | Contract, ContractParty, Customer, AccountMember, Account, Relation_3, BillingAccount, Invoice | Scans ContractParty (996), AccountMember (1,025), and Invoice (2,603); total 4,649 logical reads |
| Q2b | Retrieve billing-account invoice history directly | Transactional; per billing inquiry | Invoice | Invoice clustered-index scan, 2,603 logical reads |
| Q3 | Resolve the active rate version | Transactional per quote or refresh publish | RATE_VERSION | Clustered-index scan, 2 logical reads. The current eleven-row dimension does not justify an index by status alone. |
| Q4 | Calculate a participant's verified annual activity total | Analytical; per renewal calculation | WELLNESS_ACTIVITY | Clustered-index scan, 4,562 logical reads |
| Q5 | Calculate verified annual activity totals for all enrollments | Analytical; per renewal cycle | WELLNESS_ACTIVITY | Clustered-index scan, 4,562 logical reads; 7,988 enrollment groups returned |
| Q6 | Audit contracts pinned to one issued rate version | Analytical; per rate-version audit | Contract | Clustered-index scan, 1,424 logical reads |
| Q7 | Identify one quarter's renewals for repricing | Analytical; quarterly renewal batch | POLICY_RENEWAL | Clustered-index scan, 728 logical reads |
| Q8 | Compare selective lapsed versus non-selective active policies | Analytical selectivity contrast; design review | Contract | Two clustered-index scans, 2,848 logical reads combined |
| Q9 | Derive BRFSS prevalence profiles during asynchronous refresh | Batch; nightly or on external-data refresh | STG_BRFSS_RECORD | Two clustered-index scans, 1,240 logical reads; 1,480 prevalence rows returned |

Logical reads and actual plan shape are the reported performance measures. A
logical read counts SQL Server data pages touched and is governed by the plan
and layout, whereas the local engine runs under Rosetta 2 emulation on Apple
Silicon. Elapsed time consequently includes translation overhead that is not
representative of Azure SQL Database or native SQL Server hardware. Every query
was run twice without clearing the buffer cache; the first execution was
discarded and the second execution supplied the saved actual plan and logical
read result.

The baseline makes several physical-design candidates concrete. Q1 shows that
ContractParty.Customer_CustomerID is a response-time index candidate because a
single customer lookup scans all 90,000 party rows. Q2 traverses seven declared
relationships and adds full scans of ContractParty, AccountMember, and Invoice
to the direct Q2b Invoice scan, so the unindexed traversal foreign keys are
candidate indexes. Q2b remains a scan because Invoice.BillingAccount_BillingAccountID
is also unindexed; indexing that column would benefit both requests, while the
additional traversal indexes would address Q2 specifically.

Q4 and Q5 both scan the million-row activity table. An EnrollmentID and date
access path is a candidate for the per-renewal Q4 lookup, while the repeated
annual aggregation in Q5 is the evidence for selective materialization after
the required indexed-view eligibility analysis. The five-year ActivityDate span
also makes date partitioning a candidate for workload isolation and partition
elimination, but partitioning would add operational complexity and is not a
substitute for a selective enrollment lookup. Q6 and Q7 scan their full policy
and renewal populations, so IssuedRateVersionID and RenewalDate are index
candidates. Q8 supplies the tradeoff evidence: an ActivityStatus index is more
plausibly useful for the 8,506 lapsed policies than the 46,679 active policies,
where a scan may remain preferable. Q9 scans the individual BRFSS records twice
to build the already-defined summary grain; its batch nature favors considering
staging/refresh access paths and the retained STG_BRFSS materialization rather
than a latency-oriented lookup index.
