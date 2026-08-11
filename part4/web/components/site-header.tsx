// Jingrui Feng (jf4446) - site navigation header
import Link from "next/link";
import { DemoGuideDialog } from "@/components/demo-guide-dialog";

export function SiteHeader() {
  return <header className="border-b border-slate/10 bg-white"><div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4"><Link href="/quote" className="group"><p className="font-mono text-[10px] font-semibold tracking-[0.22em] text-active">CEDAR LEDGER LIFE</p><p className="font-display text-xl text-slate">Rate book demonstration</p></Link><nav className="hidden items-center gap-5 text-sm text-muted md:flex"><Link href="/quote" className="hover:text-ink">Quote</Link><Link href="/wellness" className="hover:text-ink">Wellness</Link><Link href="/admin/reprice" className="hover:text-ink">Rate versions</Link><Link href="/admin/analytics" className="hover:text-ink">Analytics</Link></nav><DemoGuideDialog /></div></header>;
}
