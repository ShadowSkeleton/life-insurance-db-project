// Jingrui Feng (jf4446) - demo guide dialog
"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { BookOpen, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { demoPresenterNote, demoSteps } from "@/lib/demo-guide";
import { Button } from "@/components/ui/button";

export function DemoGuideDialog() {
  const pathname = usePathname();
  return <Dialog.Root>
    <Dialog.Trigger asChild><Button variant="ghost" className="gap-2 text-xs"><BookOpen size={15} /> Demo guide</Button></Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-slate/35 backdrop-blur-[1px]" />
      <Dialog.Content className="fixed right-0 top-0 z-50 h-dvh w-full max-w-xl overflow-y-auto border-l border-slate/15 bg-paper p-6 shadow-2xl focus:outline-none">
        <div className="flex items-start justify-between gap-4"><div><Dialog.Title className="font-display text-3xl text-slate">Presentation guide</Dialog.Title><Dialog.Description className="mt-2 text-sm leading-6 text-muted">Seven observed steps, shared with the written demonstration guide.</Dialog.Description></div><Dialog.Close asChild><Button variant="ghost" aria-label="Close demonstration guide"><X size={20} /></Button></Dialog.Close></div>
        <ol className="mt-8 space-y-5">{demoSteps.map((step, index) => <li key={step.title} className={`border-l-4 pl-4 ${pathname === step.screen ? "border-active" : "border-slate/15"}`}><p className="font-mono text-xs font-semibold tracking-wide text-active">{String(index + 1).padStart(2, "0")} · {step.useCase}</p><h3 className="mt-1 font-semibold text-ink">{step.title}</h3><p className="mt-1 text-sm leading-6 text-muted">{step.text}</p></li>)}</ol>
        <p className="mt-7 border-l-4 border-active bg-white p-4 text-sm leading-6 text-muted"><span className="font-semibold text-ink">Presenter note. </span>{demoPresenterNote}</p>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
