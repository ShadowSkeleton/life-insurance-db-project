// Jingrui Feng (jf4446) - quote form and bind action
"use client";

import { FormEvent, useEffect, useState } from "react";
import { Pin, ShieldCheck } from "lucide-react";
import { AnimatedMoney } from "@/components/animated-money";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { money } from "@/lib/pricing";
import type { ProductRow } from "@/lib/types";

type Quote = { applicationId: number; premium: number; ageBand: string; bmiBand: string; rateVersionId: number; baseRate: number; mortalityMultiplier: number; priorQuote: { ApplicationID: number; QuotedPremium: number; QuotedRateVersionID: number } | null };
const fieldClass = "mt-1 block w-full border border-slate/20 bg-white px-3 py-2 text-ink outline-none transition focus:border-active focus:ring-2 focus:ring-active/20";

export default function QuotePage() {
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [binding, setBinding] = useState(false);
  const [bound, setBound] = useState<{ contractId: number; rateVersionId: number } | null>(null);
  const [form, setForm] = useState({ customerId: "1", productId: "3", age: "47", gender: "M", smokingStatus: "never", diabetesStatus: "no", bmi: "23.5", faceAmount: "250000" });

  useEffect(() => { fetch("/api/quote/options").then((r) => r.json()).then((data) => setProducts(data.products ?? [])).catch(() => setMessage("Products could not be read. Check the local connection.")); }, []);
  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));

  async function getQuote(event: FormEvent) {
    event.preventDefault(); setLoading(true); setMessage(""); setBound(null);
    try {
      const response = await fetch("/api/quote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      setQuote(data); sessionStorage.setItem("cedar-last-quote", JSON.stringify({ form, quote: data }));
    } catch (error) { setQuote(null); setMessage(error instanceof Error ? error.message : "The quote could not be created."); }
    finally { setLoading(false); }
  }

  async function bind() {
    if (!quote) return; setBinding(true); setMessage("");
    try {
      const response = await fetch("/api/bind", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ applicationId: quote.applicationId }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.message); setBound(data);
    } catch (error) { setMessage(error instanceof Error ? error.message : "The policy could not be bound."); }
    finally { setBinding(false); }
  }

  return <div className="space-y-7"><div className="grid gap-5 border-b border-slate/15 pb-7 md:grid-cols-[1fr_auto]"><div><p className="font-mono text-xs font-semibold tracking-[0.16em] text-active">UC-1 · UC-2</p><h1 className="mt-2 font-display text-4xl text-slate md:text-5xl">Quote and bind</h1><p className="mt-3 max-w-2xl text-muted">A current rate book produces a traceable quote. Binding pins the policy to that same book.</p></div><p className="max-w-xs self-end text-right text-xs leading-5 text-muted">Use an existing synthetic Customer ID as the quote owner. This supports the required APPLICATION customer relationship.</p></div>
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.75fr)]"><Card className="p-6"><form onSubmit={getQuote} className="grid gap-5 sm:grid-cols-2"><label className="text-sm font-semibold">Customer ID<input className={fieldClass} min="1" value={form.customerId} onChange={(e) => update("customerId", e.target.value)} required /></label><label className="text-sm font-semibold">Product<select className={fieldClass} value={form.productId} onChange={(e) => update("productId", e.target.value)}>{products.map((product) => <option key={product.ProductID} value={product.ProductID}>#{product.ProductID} · {product.PlanName}</option>)}</select></label><label className="text-sm font-semibold">Age<input className={fieldClass} type="number" min="18" max="99" value={form.age} onChange={(e) => update("age", e.target.value)} required /></label><label className="text-sm font-semibold">Gender<select className={fieldClass} value={form.gender} onChange={(e) => update("gender", e.target.value)}><option value="M">Male</option><option value="F">Female</option></select></label><label className="text-sm font-semibold">Smoking status<select className={fieldClass} value={form.smokingStatus} onChange={(e) => update("smokingStatus", e.target.value)}><option value="never">Never</option><option value="former">Former</option><option value="current">Current</option></select></label><label className="text-sm font-semibold">Diabetes status<select className={fieldClass} value={form.diabetesStatus} onChange={(e) => update("diabetesStatus", e.target.value)}><option value="no">No</option><option value="yes">Yes</option></select></label><label className="text-sm font-semibold">BMI<input className={fieldClass} type="number" step="0.01" min="10" max="100" value={form.bmi} onChange={(e) => update("bmi", e.target.value)} required /></label><label className="text-sm font-semibold">Face amount<select className={fieldClass} value={form.faceAmount} onChange={(e) => update("faceAmount", e.target.value)}>{[100000,250000,500000,1000000].map((amount) => <option key={amount} value={amount}>{money.format(amount)}</option>)}</select></label><div className="sm:col-span-2 border-l-2 border-active/60 bg-paper px-4 py-3 text-sm leading-6 text-muted">Exercise is not collected at application. It becomes observable through wellness enrollment, so it supports renewal pricing rather than the initial quote.</div><div className="sm:col-span-2"><Button type="submit" disabled={loading}>{loading ? "Getting quote…" : "Get quote"}</Button></div></form></Card>
      <aside aria-live="polite">{quote ? <Card className="fade-in overflow-hidden"><div className="bg-slate p-6 text-white"><p className="font-mono text-xs tracking-[0.16em] text-[#A8E1E0]">QUOTE</p><AnimatedMoney value={quote.premium} className="nums mt-4 block text-5xl font-semibold tracking-tight" /><p className="mt-2 text-sm text-slate-200">Annual premium for selected face amount</p></div><div className="grid gap-4 p-6"><div className="grid grid-cols-2 gap-4 border-b border-slate/10 pb-4 text-sm"><div><p className="text-muted">Rate version</p><p className="nums mt-1 font-semibold text-ink">v{quote.rateVersionId}</p></div><div><p className="text-muted">Risk multiplier</p><p className="nums mt-1 font-semibold text-ink">{quote.mortalityMultiplier.toFixed(3)}</p></div><div><p className="text-muted">Age band</p><p className="nums mt-1 font-semibold text-ink">{quote.ageBand}</p></div><div><p className="text-muted">BMI band</p><p className="nums mt-1 font-semibold text-ink">{quote.bmiBand}</p></div></div>{quote.priorQuote && <div className="border-l-4 border-active bg-paper p-4"><p className="font-mono text-xs font-semibold tracking-[0.14em] text-active">RATE-BOOK COMPARISON</p><div className="nums mt-3 grid grid-cols-2 gap-3 text-sm"><div><p className="text-muted">Previous · v{quote.priorQuote.QuotedRateVersionID}</p><p className="mt-1 font-semibold">{money.format(quote.priorQuote.QuotedPremium)}</p></div><div><p className="text-muted">Current · v{quote.rateVersionId}</p><p className="mt-1 font-semibold">{money.format(quote.premium)}</p></div></div><p className="nums mt-3 text-sm font-semibold text-ink">{quote.premium - quote.priorQuote.QuotedPremium >= 0 ? "+" : ""}{money.format(quote.premium - quote.priorQuote.QuotedPremium)} · {((quote.premium - quote.priorQuote.QuotedPremium) * 100 / quote.priorQuote.QuotedPremium).toFixed(2)}%</p></div>}<p className="text-sm text-muted">Application <span className="nums font-semibold text-ink">#{quote.applicationId}</span> is saved as quoted.</p>{bound ? <div className="border-l-4 border-active bg-paper p-4"><p className="flex items-center gap-2 font-semibold text-ink"><Pin size={16} className="text-active" /> Policy bound</p><p className="mt-2 text-sm text-muted">Contract <span className="nums font-semibold text-ink">#{bound.contractId}</span> is pinned to rate version <span className="nums font-semibold text-ink">v{bound.rateVersionId}</span>.</p></div> : <Button onClick={bind} disabled={binding}>{binding ? "Binding policy…" : "Bind policy"}</Button>}</div></Card> : <Card className="p-6"><ShieldCheck className="text-muted" size={28}/><h2 className="mt-4 font-display text-2xl text-slate">Quote result</h2><p className="mt-2 text-sm leading-6 text-muted">The premium, multiplier, application ID, and rate version will appear here after a successful query.</p></Card>}{message && <p className="mt-3 border-l-4 border-old bg-white p-3 text-sm text-ink">{message}</p>}</aside></div></div>;
}
