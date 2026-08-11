// Jingrui Feng (jf4446) - premium transition display
"use client";

import { useEffect, useRef, useState } from "react";
import { money } from "@/lib/pricing";

export function AnimatedMoney({ value, className = "" }: { value: number; className?: string }) {
  const previous = useRef(value);
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    const start = previous.current;
    const change = value - start;
    const began = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      const progress = Math.min((now - began) / 520, 1);
      setDisplay(start + change * (1 - Math.pow(1 - progress, 3)));
      if (progress < 1) frame = requestAnimationFrame(draw); else previous.current = value;
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <span className={className}>{money.format(display)}</span>;
}
