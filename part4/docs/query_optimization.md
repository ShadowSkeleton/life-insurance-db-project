# Jingrui Feng (jf4446) - database systems project part 4 - query optimization

## Measurement method

I reported logical reads and plan shape rather than elapsed time. Local SQL Server ran under Rosetta 2 emulation on Apple Silicon. Elapsed time there included instruction translation. Logical reads counted the pages each plan touched, so they reflected the access path rather than the hardware. I used the same method in Part 3. The Part 4 figures are therefore comparable to the Part 3 figures.

## 1. The indexed view as selective denormalization

I materialized the annual wellness aggregate as `dbo.vWellnessActivityEnrollmentYear`. Its unique clustered index used `(ActivityYear, EnrollmentID)` with `FILLFACTOR = 80`. `WELLNESS_ACTIVITY` held 1,000,000 rows. The view stored the annual result rather than recomputing it from those rows. This was denormalization in the sense required by the specification.

I measured the yearly question with `WITH (NOEXPAND)`. One enrollment read 2 logical pages. All enrollments read 34 logical pages. The equivalent questions against the partitioned base table read 7 and 423 logical pages. The view made the annual query selective because it stored the result at the same annual enrollment grain.

Part 3 established an important limit. The optimizer did not automatically use this view for a date-range predicate because it could not prove that the date expression equaled the view's year grouping. The default date-range plans correctly used the base table. Materialization helped only after I asked the question at the yearly grain. Storage alone did not help.

The view added 1,032 KB. The final database occupied 215,112 KB. I accepted that storage cost because the all-enrollment annual question fell from 423 reads to 34 reads.

## 2. The renewal effective premium access pattern

Part 4 added `POLICY_RENEWAL` writes. This raised the question of how a current effective premium would be retrieved. The needed pattern joins the latest renewal and falls back to `Contract.ModalPremium` when no renewal exists. I measured that correlated top-one-per-group access pattern before deciding whether it needed an index. `POLICY_RENEWAL` held 90,000 rows.

The existing unique key produced 5 logical reads. Its plan used a backward index seek and a primary-key lookup. Forcing `INDEX(0)` produced 728 logical reads. Its plan used a clustered scan and a Top 1 sort. SQL Server satisfied `RenewalDate DESC, RenewalID DESC` through a backward seek on the ascending `(ContractID, RenewalDate)` key. I measured before adding a descending index and did not add one.

I added `UQ_POLICY_RENEWAL_ContractID_RenewalDate` to enforce one renewal for each contract and renewal date. That correctness guarantee allowed the renewal route to move from serializable to read committed isolation. The same key also served the measured retrieval pattern.

The application did not yet expose the effective-premium query. The renewal route used this date-specific lookup instead:

```sql
SELECT TOP (1) RenewalID, ContractID,
       CONVERT(VARCHAR(10), RenewalDate, 23) AS RenewalDate,
       NewRateVersionID, WellnessDiscountPct, FinalPremium
FROM dbo.POLICY_RENEWAL
WHERE ContractID = @contractId AND RenewalDate = @renewalDate
ORDER BY RenewalID DESC;
```

The effective-premium pattern remained measured design work for a retrieval the application would need if it displayed current premiums instead of issue-time premiums.

## 3. The ORM boundary

I integrated Prisma on 2 routes as the item 4 extra credit. I kept the remaining routes on the `mssql` driver. This was a measured split, not a framework limitation. Prisma generated compile-time types across 44 introspected models.

`GET /api/quote/options` replaced this hand-written statement:

```sql
SELECT ProductID, LineOfBusiness, SeriesName, PlanName, Description
FROM dbo.Product
ORDER BY ProductID;
```

Prisma emitted this statement for the same route:

```sql
SELECT [dbo].[Product].[ProductID], [dbo].[Product].[LineOfBusiness], [dbo].[Product].[SeriesName], [dbo].[Product].[PlanName], [dbo].[Product].[Description]
FROM [dbo].[Product]
WHERE 1=1
ORDER BY [dbo].[Product].[ProductID] ASC
OFFSET @P1 ROWS
```

Both statements read 2 logical pages. Prisma did not improve performance here. It cost nothing for this 15-row product-options lookup and gave the route generated types.

The wellness aggregation had a different boundary. Prisma had no model for `vWellnessActivityEnrollmentYear` because view introspection was a preview feature that I did not enable. Its query API could not emit the SQL Server `NOEXPAND` table hint. The closest ORM expression was a `groupBy` against `WELLNESS_ACTIVITY`. It read 7 logical pages for one enrollment and 423 for all enrollments, instead of 2 and 34 through the indexed view.

Prisma offered `$queryRaw`. A parameterized `$queryRaw` with `FROM dbo.vWellnessActivityEnrollmentYear WITH (NOEXPAND)` would preserve the hint because it supplied the SQL literally. Prisma could therefore carry every path. At that point it would contribute a connection and no query generation. I kept the measured aggregation and pricing paths on the driver for that reason. Prisma did not improve performance anywhere.

## 4. Inherited Part 3 optimizations

I retained the Part 3 `ContractParty.Customer_CustomerID` covering index. It reduced the one-customer policy lookup from 999 to 5 logical reads across `ContractParty` and `Contract`. I retained the wellness index on `(EnrollmentID, ActivityDate)` with `VerifiedFlag` included. It made the qualifying-count aggregation covering and reduced the single-enrollment workload from 4,562 to 7 reads.

I retained yearly partitioning for the 1,000,000-row `WELLNESS_ACTIVITY` table and the 300,000-row `Invoice` table. The 2025 wellness aggregation accessed 1 of 6 partitions and fell from 2,794 to 423 logical reads. Invoice queries without a `RunDate` predicate touched all 6 partitions, so partitioning did not improve them. The aligned date layout helped only where the query supplied a yearly boundary.

I also retained the cases where SQL Server correctly declined an index. The rate-version audit returned 12,448 of 60,000 contracts, or 20.7 percent, and stayed a 1,424-read clustered scan. The renewal worklist returned 7,548 of 90,000 renewals, or 8.4 percent, and stayed a 728-read clustered scan. The final physical design occupied 215,112 KB, up from 140,000 KB at baseline. I accepted the 53.65 percent storage increase where the measured access paths reduced reads.
