// Jingrui Feng (jf4446) - Prisma client for the two scoped ORM routes
import "server-only";
import path from "node:path";
import { config as loadEnv } from "dotenv";
import { PrismaMssql } from "@prisma/adapter-mssql";
import { PrismaClient } from "../generated/prisma-client/client";

loadEnv({ path: path.resolve(process.cwd(), "..", ".env") });

declare global {
  // eslint-disable-next-line no-var
  var cedarLedgerPrisma: PrismaClient | undefined;
}

function prismaAdapter(): PrismaMssql {
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
  return new PrismaMssql({
    server,
    database,
    user,
    password,
    port: isAzure ? 1433 : Number(process.env.MSSQL_PORT ?? 1433),
    options: { encrypt: true, trustServerCertificate: !isAzure },
  });
}

export const prisma = global.cedarLedgerPrisma ?? new PrismaClient({ adapter: prismaAdapter() });

if (process.env.NODE_ENV !== "production") {
  global.cedarLedgerPrisma = prisma;
}
