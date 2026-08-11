// Jingrui Feng (jf4446) - shared card component
import { cn } from "@/lib/utils";
export function Card({ className, children }: React.PropsWithChildren<{ className?: string }>) {
  return <section className={cn("border border-slate/10 bg-white shadow-[0_10px_25px_rgba(23,32,51,0.05)]", className)}>{children}</section>;
}
