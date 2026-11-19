"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "../lib/format";

type Summary = { count: number; value: number; untradeable: number; loans?: number };

/** Resumen del club en la portada: jugadores, valor, intransferibles y cesiones. */
export default function HomeStats({ apiUrl }: { apiUrl: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiUrl}/club?page=1&page_size=1`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((b: { summary: Summary }) => setSummary(b.summary))
      .catch(() => {});
    return () => controller.abort();
  }, [apiUrl]);

  if (!summary) return null;
  const stats: [string, string][] = [
    ["Jugadores", formatNumber(summary.count)],
    ["Valor del club", `${formatNumber(summary.value)} monedas`],
    ["Intransferibles", formatNumber(summary.untradeable)],
    ["Cedidos", formatNumber(summary.loans ?? 0)],
  ];
  return (
    <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map(([label, value]) => (
        <div key={label} className="rounded-card border border-line bg-surface p-4">
          <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
          <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
