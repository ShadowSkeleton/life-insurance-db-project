import path from "node:path";
import { config as loadEnv } from "dotenv";
import { defineConfig } from "prisma/config";

loadEnv({ path: path.resolve(process.cwd(), "..", ".env") });

const target = process.env.DATABASE_TARGET;
if (target !== "local" && target !== "azure") {
  throw new Error("Set DATABASE_TARGET to local or azure in the parent Part 4 .env file.");
}

const isAzure = target === "azure";
const server = isAzure ? process.env.AZURE_SQL_SERVER : process.env.MSSQL_HOST;
const database = isAzure ? process.env.AZURE_SQL_DATABASE : process.env.MSSQL_DATABASE;
const username = isAzure ? process.env.AZURE_SQL_USER : process.env.MSSQL_USER;
const password = isAzure ? process.env.AZURE_SQL_PASSWORD : process.env.MSSQL_SA_PASSWORD;
const port = isAzure ? 1433 : Number(process.env.MSSQL_PORT ?? 1433);

if (!server || !database || !username || !password) {
  throw new Error(`Database settings are incomplete for DATABASE_TARGET=${target}.`);
}

const databaseUrl = `sqlserver://${server}:${port};database=${database};username=${username};password=${encodeURIComponent(password)};encrypt=true;trustServerCertificate=${!isAzure};schema=dbo;`;

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: databaseUrl,
  },
});
