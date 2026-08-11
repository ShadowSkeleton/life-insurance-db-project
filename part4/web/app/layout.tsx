// Jingrui Feng (jf4446) - application layout
import type { Metadata } from "next";
import "@/app/globals.css";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Cedar Ledger Life | Rate book demonstration", description: "Course demonstration using synthetic policy data." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><SiteHeader /><main className="mx-auto min-h-[calc(100vh-73px)] max-w-7xl px-5 py-8">{children}</main><footer className="border-t border-slate/10 bg-white px-5 py-4 text-center text-xs text-muted">Course demonstration using synthetic policy data and Azure SQL analytics.</footer></body></html>;
}
