// Jingrui Feng (jf4446) - database connection pool
import "server-only";
import path from "node:path";
import { config as loadEnv } from "dotenv";
import sql from "mssql";

// Next.js replaces modules during hot reload. Keeping one pool on globalThis
// prevents each save from opening another SQL Server connection.
loadEnv({ path: path.resolve(process.cwd(), "..", ".env") });

declare global {
  // eslint-disable-next-line no-var
  var cedarLedgerPool: sql.ConnectionPool | undefined;
}

function databaseConfig(): sql.config {
  const target = process.env.DATABASE_TARGET;
  if (target !== "local" && target !== "azure") {
    throw new Error("Set DATABASE_TARGET to either local or azure in the server-side Part 4 .env file.");
  }
  const isAzure = target === "azure";
  const server = isAzure ? process.env.AZURE_SQL_SERVER : process.env.MSSQL_HOST;
  const database = isAzure ? process.env.AZURE_SQL_DATABASE : process.env.MSSQL_DATABASE;
  const user = isAzure ? process.env.AZURE_SQL_USER : process.env.MSSQL_USER;
  const password = isAzure ? process.env.AZURE_SQL_PASSWORD : process.env.MSSQL_SA_PASSWORD;
  if (!server || !database || !user || !password) {
    throw new Error("Database settings are incomplete. Check the server-side Part 4 .env file.");
  }
  return {
    server,
    database,
    user,
    password,
    port: isAzure ? 1433 : Number(process.env.MSSQL_PORT ?? 1433),
    options: { encrypt: true, trustServerCertificate: !isAzure },
    pool: { max: 10, min: 0, idleTimeoutMillis: 30000 },
  };
}

export async function getPool(): Promise<sql.ConnectionPool> {
  if (!global.cedarLedgerPool) {
    global.cedarLedgerPool = await new sql.ConnectionPool(databaseConfig()).connect();
  }
  return global.cedarLedgerPool;
}

export { sql };
