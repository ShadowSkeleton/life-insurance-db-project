// Jingrui Feng (jf4446) - shared button component
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-sm text-sm font-semibold transition duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-active focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  { variants: { variant: { default: "bg-active px-4 py-2 text-white hover:bg-[#00656b]", secondary: "border border-slate/20 bg-white px-4 py-2 text-ink hover:bg-paper", ghost: "px-3 py-2 text-ink hover:bg-paper" } }, defaultVariants: { variant: "default" } },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean; }
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, asChild, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant }), className)} ref={ref} {...props} />;
});
Button.displayName = "Button";
