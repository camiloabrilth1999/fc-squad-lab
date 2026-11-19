"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "../lib/format";

type Reward = { stat: number; name: string; count: number; max_value: number | null };
type Upgrade = { stat: number; name: string; total: number; initial: number | null };
type Level = {
  level: number;
  state: string | null;
  objectives: { id: number | null; name: string; description: string | null }[];
  awards: Reward[];
};
type Evolution = {
  id: number;
  name: string | null;
  description: string | null;
  status: string | null;
  category_id: number | null;
  category: string | null;
  timed: boolean;
  ends_at: string | null;
  gk_only: boolean;
  outfield_only: boolean;
  multi_choice: boolean;
  total_rewards: number | null;
  cost: Record<string, unknown>[];
  top_rewards: Reward[];
  upgrades: Upgrade[];
  levels: Level[];
  requirements: unknown[];
};
type Category = { id: number; name: string; total: number; imported: number };

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: "Disponible",
  STARTED: "En curso",
  ACTIVE: "Activa",
  COMPLETE: "Completada",
  READY_FOR_REDEEM: "Lista para reclamar",
  EXPIRED: "Caducada",
  LOCKED: "Bloqueada",
};

/** "1 día", "5 horas"… hasta la fecha; "caducada" si ya pasó. */
export function formatRemaining(iso: string | null, now: number = Date.now()): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now;
  if (Number.isNaN(ms)) return null;
  if (ms <= 0) return "caducada";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return `${Math.max(1, Math.floor(ms / 60_000))} min`;
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(hours / 24)} días`;
}

function costLabel(c: Record<string, unknown>): string {
  const amount = c.amount ?? c.value ?? c.price;
  const kind = String(c.currency ?? c.type ?? "").toUpperCase();
  if (typeof amount === "number") {
    if (kind.includes("COIN")) return `${formatNumber(amount)} monedas`;
    if (kind.includes("POINT") || kind.includes("FC")) return `${formatNumber(amount)} FC Points`;
    return `${formatNumber(amount)} ${kind.toLowerCase()}`.trim();
  }
  return JSON.stringify(c);
}

export default function EvolutionsBrowser({ apiUrl }: { apiUrl: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const [items, setItems] = useState<Evolution[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/evolutions/categories`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((body: unknown) => setCategories(Array.isArray(body) ? (body as Category[]) : []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl]);

  useEffect(() => {
    const ctrl = new AbortController();
    const p = new URLSearchParams({ limit: "200" });
    if (category !== null) p.set("category_id", String(category));
    if (applied.trim()) p.set("q", applied.trim());
    fetch(`${apiUrl}/evolutions?${p}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: { items: Evolution[] }) => {
        setItems(body.items);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, category, applied]);

  const pick = (id: number | null) => {
    setItems(null);
    setCategory(id);
  };

  return (
    <div className="mt-6 space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => pick(null)}
          aria-pressed={category === null}
          className={`rounded-full border px-3 py-1 text-sm ${
            category === null ? "border-accent bg-surface-2 font-medium" : "border-line text-muted hover:text-fg"
          }`}
        >
          Todas
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => pick(c.id)}
            aria-pressed={category === c.id}
            className={`rounded-full border px-3 py-1 text-sm ${
              category === c.id ? "border-accent bg-surface-2 font-medium" : "border-line text-muted hover:text-fg"
            }`}
          >
            {c.name}{" "}
            <span className="text-xs text-muted">
              {c.imported}/{c.total}
            </span>
          </button>
        ))}
        <form
          className="ml-auto flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setItems(null);
            setApplied(q);
          }}
        >
          <input
            aria-label="Buscar evolución"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar…"
            className="w-44 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg hover:bg-accent-strong"
          >
            Buscar
          </button>
        </form>
      </div>

      {failed ? <p className="text-danger">No se pudieron cargar las evoluciones.</p> : null}
      {!items && !failed ? <p className="text-muted">Cargando…</p> : null}
      {items && items.length === 0 ? (
        <div className="rounded-card border border-dashed border-line bg-surface p-8 text-center text-muted">
          Aún no hay evoluciones aquí. Abre <strong>Evoluciones</strong> en la web app de EA con la
          extensión activa y se importan solas.
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(items ?? []).map((e) => {
          const remaining = formatRemaining(e.ends_at);
          const extra = Math.max(0, (e.total_rewards ?? 0) - e.top_rewards.length);
          const isOpen = open === e.id;
          return (
            <article key={e.id} className="flex flex-col rounded-card border border-line bg-surface p-4">
              <header className="flex items-start justify-between gap-2">
                <h3 className="font-semibold">{e.name ?? "Evolución"}</h3>
                {e.status ? (
                  <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
                    {STATUS_LABEL[e.status] ?? e.status}
                  </span>
                ) : null}
              </header>
              <p className="mt-1 text-xs text-muted">
                {[e.category, e.gk_only ? "solo porteros" : e.outfield_only ? "solo jugadores de campo" : null]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {e.description ? (
                <p className="mt-2 line-clamp-3 text-sm text-muted">{e.description}</p>
              ) : null}

              {e.top_rewards.length > 0 ? (
                <ul className="mt-3 space-y-0.5 text-sm">
                  {e.top_rewards.map((r) => (
                    <li key={r.stat} className="flex justify-between gap-3">
                      <span>{r.name}</span>
                      <span className="font-mono tabular-nums">
                        +{r.count}
                        {r.max_value ? <span className="text-xs text-muted"> (máx. {r.max_value})</span> : null}
                      </span>
                    </li>
                  ))}
                  {extra > 0 ? <li className="text-xs text-accent">+{extra} más</li> : null}
                </ul>
              ) : null}

              <footer className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                {e.cost.length > 0 ? <span>Coste: {e.cost.map(costLabel).join(" + ")}</span> : <span>Gratis</span>}
                {remaining ? <span>Expira en {remaining}</span> : null}
                {e.levels.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : e.id)}
                    aria-expanded={isOpen}
                    className="ml-auto text-accent hover:underline"
                  >
                    {isOpen ? "Ocultar niveles" : `Ver ${e.levels.length - 1} niveles`}
                  </button>
                ) : null}
              </footer>

              {isOpen ? (
                <ol className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
                  {e.levels
                    .filter((l) => l.objectives.length > 0 || l.awards.length > 0)
                    .map((l) => (
                      <li key={l.level}>
                        <p className="font-medium">Nivel {l.level}</p>
                        {l.objectives.map((o) => (
                          <p key={o.id ?? o.name} className="text-muted">
                            {o.name}
                          </p>
                        ))}
                        {l.awards.length > 0 ? (
                          <p className="text-xs text-accent">
                            {l.awards.map((a) => `${a.name} +${a.count}`).join(" · ")}
                          </p>
                        ) : null}
                      </li>
                    ))}
                </ol>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
