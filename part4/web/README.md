# Cedar Ledger Life demonstration

This is a local-only Next.js demonstration of the Part 3 rate engine. It uses
synthetic policy data in the local SQL Server database and implements the quote,
wellness, and rate-revision workflows.

## Run

From `part3/web`, install packages with `npm install`, then run `npm run dev`.
Open `http://localhost:3000/quote`.

The server reads connection settings from `part3/.env`, not from browser code.
For local SQL Server it requires `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`,
`MSSQL_SA_PASSWORD`, and `MSSQL_DATABASE`. To repoint without code changes,
set `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`, `AZURE_SQL_USER`, and
`AZURE_SQL_PASSWORD` instead. Azure settings take precedence and enable
certificate validation.

The rate-refresh button invokes the existing server-side
`python/etl/run_rate_refresh.py`. It is deliberately not reimplemented in
TypeScript so the local demonstration and the deployed Azure Function use one
pricing implementation. `func-dbp3-raterefresh` runs the same refresh core on
the first day of each month at 02:00 UTC.

## Design plan

The palette is slate `#172033`, paper-blue `#F3F7FA`, ink `#263244`, muted
`#697586`, active teal `#007C83`, and superseded taupe `#7D6F64`. Source Sans
3 carries interface text, Newsreader carries headings, and JetBrains Mono carries
all numeric figures with tabular numerals. The layout uses a policy and rate-book
ledger rather than a marketing page. Its signature element is the explicit
version pin shown next to a quoted and then bound policy.

The guide overlay imports `web/lib/demo-guide-content.json`. `npm run dev` and
`npm run build` run `guide:sync`, which regenerates `docs/demo_guide.md` from
that same file. The two guides therefore cannot drift.
