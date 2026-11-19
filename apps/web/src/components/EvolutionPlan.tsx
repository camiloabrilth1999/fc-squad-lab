"use client";

import { useEffect, useState } from "react";

type Assignment = {
  evolution: { id: number; name: string | null; category: string | null };
  card: { item_id: number; name: string | null; rating: number | null; positions: string[] };
  meta_before: number;
  meta_after: number;
  meta_gain: number;
};
type Plan = { assignments: Assignment[]; total_gain: number; evolutions_considered: number };

export default function EvolutionPlan({ apiUrl }: { apiUrl: string }) {
  const [minAfter, setMinAfter] = useState("70");
  const [applied, setApplied] = useState("70");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/evolutions/plan?min_after=${encodeURIComponent(applied || "0")}`, {
      signal: ctrl.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: Plan) => {
        setPlan(body);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, applied]);

  return (
    <section
      aria-label="Plan para tu club"
      className="rounded-card border border-line bg-surface p-5"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Plan para tu club</h2>
          <p className="text-sm text-muted">
            Qué evolución dar a qué carta para subir más el meta en total. Una evolución y una
            carta, una sola vez.
          </p>
        </div>
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPlan(null);
            setApplied(minAfter);
          }}
        >
          <label className="text-sm">
            <span className="mb-1 block text-muted">Meta final mínimo</span>
            <input
              type="number"
              min={0}
              max={100}
              value={minAfter}
              onChange={(e) => setMinAfter(e.target.value)}
              className="w-24 rounded-lg border border-line bg-surface-2 px-3 py-1.5"
            />
          </label>
          <button
            type="submit"
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg hover:bg-accent-strong"
          >
            Calcular
          </button>
        </form>
      </div>

      {failed ? <p className="mt-3 text-danger">No se pudo calcular el plan.</p> : null}
      {!plan && !failed ? <p className="mt-3 text-muted">Calculando…</p> : null}
      {plan && plan.assignments.length === 0 ? (
        <p className="mt-3 text-muted">
          Ninguna evolución mejora una carta tuya con ese meta final mínimo.
        </p>
      ) : null}
      {plan && plan.assignments.length > 0 ? (
        <>
          <p className="mt-3 text-sm">
            Mejora total: <span className="font-semibold text-accent">+{plan.total_gain.toFixed(1)}</span>{" "}
            <span className="text-muted">
              ({plan.assignments.length} de {plan.evolutions_considered} evoluciones)
            </span>
          </p>
          <ul className="mt-2 divide-y divide-line text-sm">
            {plan.assignments.map((a) => (
              <li key={a.evolution.id} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2">
                <span className="font-medium">{a.evolution.name ?? "Evolución"}</span>
                <span className="text-muted">
                  {a.card.name ?? "Carta"} · {a.card.rating} · {a.card.positions.slice(0, 2).join("/")}
                </span>
                <span className="font-mono text-xs tabular-nums">
                  {a.meta_before.toFixed(1)} → {a.meta_after.toFixed(1)}{" "}
                  <span className="text-accent">(+{a.meta_gain.toFixed(1)})</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
