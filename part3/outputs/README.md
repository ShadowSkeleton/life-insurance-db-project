# Jingrui Feng (jf4446) - database systems project part 3 - measurement output convention

# Measurement-output convention

Every `query_summary_all_tables.csv` in this directory uses one convention:
logical reads are summed across all user tables touched by a query according to
the second execution's `SET STATISTICS IO` output. The per-table result CSVs
remain available for plan diagnosis, while the summary CSVs are the figures used
for cross-query comparison and report tables. Under this convention, baseline
Q1 is 999 reads rather than the 996 reads of ContractParty alone.

`baseline`, `increment1`, and `increment2` are preserved historical captures.
`increment3` records the superseded daily indexed-view experiment. `corrections`
contains the final current workload, the yearly-view rebuild, the four Q8
variants, and the indexed-view `NOEXPAND` fallback measurements.
