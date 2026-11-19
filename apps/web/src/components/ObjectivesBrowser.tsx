"use client";

import { useEffect, useState } from "react";
import { formatRemaining } from "../lib/format";

type Award = { type: string; label: string; count: number };
type Task = {
  id: number;
  name: string;
  description: string | null;
  progress: number | null;
  target: number | null;
  state: string | null;
  awards: Award[];
};
type Group = {
  id: number;
  type: number;
  title: string | null;
  subtitle: string | null;
  category_id: number | null;
  category: string | null;
  status: "not_started" | "in_progress" | "done";
  repeatability: string | null;
  times_completed: number;
  ends_at: string | null;
  progress: { done: number; total: number };
  awards: Award[];
  objectives: Task[];
};
type Category = { id: number; name: string; groups: number; done: number };

const STATUS: Record<Group["status"], { label: string; cls: string }> = {
  not_started: { label: "Sin empezar", cls: "bg-surface-2 text-muted" },
  in_progress: { label: "En curso", cls: "bg-warn/15 text-warn" },
  done: { label: "Completado", cls: "bg-accent text-accent-fg" },
};
const FILTERS: [string, string][] = [
  ["", "Todos"],
  ["open", "Pendientes"],
  ["done", "Completados"],
];

/** Caduca en menos de 48 h (y aún no ha caducado). */
function endsSoon(iso: string | null): boolean {
  if (!iso) return false;
  const ms = new Date(iso).getTime() - Date.now();
  return ms > 0 && ms < 48 * 3_600_000;
}

export default function ObjectivesBrowser({ apiUrl }: { apiUrl: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<number | null>(null);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const [items, setItems] = useState<Group[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/objectives/categories`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((body: unknown) => setCategories(Array.isArray(body) ? (body as Category[]) : []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl]);

  useEffect(() => {
    const ctrl = new AbortController();
    const p = new URLSearchParams({ limit: "300" });
    if (category !== null) p.set("category_id", String(category));
    if (status) p.set("status", status);
    if (applied.trim()) p.set("q", applied.trim());
    fetch(`${apiUrl}/objectives?${p}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: { items: Group[] }) => {
        setItems(body.items);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, category, status, applied]);

  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-sm ${
      active ? "border-accent bg-surface-2 font-medium" : "border-line text-muted hover:text-fg"
    }`;

  return (
    <div className="mt-6 space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-pressed={category === null}
          className={chip(category === null)}
          onClick={() => {
            setItems(null);
            setCategory(null);
          }}
        >
          Todas
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            aria-pressed={category === c.id}
            className={chip(category === c.id)}
            onClick={() => {
              setItems(null);
              setCategory(c.id);
            }}
          >
            {c.name}{" "}
            <span className="text-xs text-muted">
              {c.done}/{c.groups}
            </span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-line p-0.5 text-sm">
          {FILTERS.map(([value, label]) => (
            <button
              key={label}
              type="button"
              aria-pressed={status === value}
              onClick={() => {
                setItems(null);
                setStatus(value);
              }}
              className={`rounded-md px-3 py-1 ${
                status === value ? "bg-surface-2 font-medium" : "text-muted hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setItems(null);
            setApplied(q);
          }}
        >
          <input
            aria-label="Buscar objetivo"
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

      {failed ? <p className="text-danger">No se pudieron cargar los objetivos.</p> : null}
      {!items && !failed ? <p className="text-muted">Cargando…</p> : null}
      {items && items.length === 0 ? (
        <div className="rounded-card border border-dashed border-line bg-surface p-8 text-center text-muted">
          Aún no hay objetivos aquí. Abre <strong>FC Hub → Objetivos</strong> en la web app de EA con
          la extensión activa y se importan solos.
        </div>
      ) : null}

      {items && items.length > 0 ? (
        <dl className="grid grid-cols-3 gap-3">
          {(
            [
              ["Total", items.length],
              ["Hechos", items.filter((g) => g.status === "done").length],
              ["Por caducar", items.filter((g) => g.status !== "done" && endsSoon(g.ends_at)).length],
            ] as [string, number][]
          ).map(([label, n]) => (
            <div key={label} className="rounded-card border border-line bg-surface p-3">
              <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
              <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{n}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(items ?? []).map((g) => {
          const key = `${g.type}-${g.id}`;
          const st = STATUS[g.status];
          const remaining = formatRemaining(g.ends_at);
          const urgent = g.status !== "done" && endsSoon(g.ends_at);
          const pct = g.progress.total ? Math.round((g.progress.done / g.progress.total) * 100) : 0;
          const isOpen = open === key;
          return (
            <article
              key={key}
              className={`flex flex-col rounded-card border border-l-4 bg-surface p-4 ${
                urgent ? "border-warn/60 border-l-warn" : g.status === "done" ? "border-line border-l-accent" : "border-line border-l-line"
              }`}
            >
              <header className="flex items-start justify-between gap-2">
                <h3 className="font-semibold">{g.title ?? "Objetivos"}</h3>
                <span className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] ${st.cls}`}>{st.label}</span>
              </header>
              <p className="mt-1 text-xs text-muted">
                {[g.category, g.repeatability === "REFRESH" ? "se renueva" : null].filter(Boolean).join(" · ")}
              </p>
              {g.subtitle ? <p className="mt-2 line-clamp-2 text-sm text-muted">{g.subtitle}</p> : null}

              {g.progress.total > 0 ? (
                <div className="mt-3">
                  <div
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Progreso de ${g.title ?? "objetivos"}`}
                    className="h-1.5 overflow-hidden rounded bg-surface-2"
                  >
                    <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {g.progress.done}/{g.progress.total} objetivos
                  </p>
                </div>
              ) : null}

              {g.awards.length > 0 ? (
                <p className="mt-3 text-sm">
                  <span className="text-muted">Recompensas: </span>
                  {g.awards.map((a) => a.label).join(" · ")}
                </p>
              ) : null}

              <footer className="mt-3 flex items-center gap-3 text-xs text-muted">
                {remaining ? (
                  <span className={urgent ? "font-medium text-warn" : ""}>Termina en {remaining}</span>
                ) : null}
                {g.objectives.length > 0 ? (
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpen(isOpen ? null : key)}
                    className="ml-auto text-accent hover:underline"
                  >
                    {isOpen ? "Ocultar" : `Ver ${g.objectives.length} objetivos`}
                  </button>
                ) : null}
              </footer>

              {isOpen ? (
                <ul className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
                  {g.objectives.map((t) => (
                    <li key={t.id}>
                      <div className="flex justify-between gap-3">
                        <span>{t.name}</span>
                        <span className="shrink-0 font-mono text-xs tabular-nums text-muted">
                          {t.state === "REDEEMED" ? "✓" : `${t.progress ?? 0}/${t.target ?? "?"}`}
                        </span>
                      </div>
                      {t.awards.length > 0 ? (
                        <p className="text-xs text-accent">{t.awards.map((a) => a.label).join(" · ")}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
