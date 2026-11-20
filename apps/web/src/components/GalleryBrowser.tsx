"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber } from "../lib/format";
import CardImage, { Badge } from "./CardImage";

type Grade = { name: string; threshold: number; tokens: number };
type GallerySet = {
  id: number;
  name: string;
  group: string;
  group_name: string;
  required: number;
  tokens: number;
  image_path?: string | null;
  grades: Grade[];
  collected: number;
  points: number;
  grade: string | null;
};
type SolCard = {
  resource_id: number;
  name: string | null;
  rating: number | null;
  positions: string[];
  image_path: string | null;
  points: number;
  exact: boolean;
  price: number | null;
  collected: boolean;
};
type Solution = {
  set_id: number;
  name: string;
  grade: string;
  threshold: number;
  required: number;
  status: string;
  points: number;
  cost: number;
  tax: number;
  coins_needed: number;
  buys: number;
  estimated: boolean;
  cards: SolCard[];
};

const GRADE_CLS: Record<string, string> = {
  D: "border-orange-700 text-orange-300",
  C: "border-zinc-400 text-zinc-200",
  B: "border-amber-500 text-amber-300",
  A: "border-emerald-500 text-emerald-300",
  S: "border-sky-400 text-sky-300",
};

const STATUS: Record<string, string> = {
  optimal: "Solución óptima",
  feasible: "Solución encontrada",
  reached: "Ya alcanzas este grado",
  infeasible: "No se puede alcanzar con las cartas con precio",
  unknown: "Sin solución en el tiempo límite",
};

export default function GalleryBrowser({ apiUrl }: { apiUrl: string }) {
  const [sets, setSets] = useState<GallerySet[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [group, setGroup] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<GallerySet | null>(null);
  const [grade, setGrade] = useState("A");
  const [complete, setComplete] = useState(true);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [solving, setSolving] = useState(false);
  const [solveError, setSolveError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/gallery`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((b: { items: GallerySet[] }) => {
        setSets(b.items);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl]);

  const groups = useMemo(() => {
    const seen = new Map<string, string>();
    for (const s of sets ?? []) if (!seen.has(s.group)) seen.set(s.group, s.group_name);
    return [...seen.entries()];
  }, [sets]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (sets ?? []).filter(
      (s) => (!group || s.group === group) && (!q || s.name.toLowerCase().includes(q)),
    );
  }, [sets, group, query]);

  const solve = async (s: GallerySet, g: string, c: boolean) => {
    setSolving(true);
    setSolution(null);
    setSolveError(false);
    try {
      const r = await fetch(`${apiUrl}/gallery/${s.id}/solve?grade=${g}&complete=${c}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSolution((await r.json()) as Solution);
    } catch {
      setSolveError(true);
    } finally {
      setSolving(false);
    }
  };

  const open = (s: GallerySet) => {
    setSelected(s);
    setSolution(null);
    setSolveError(false);
    // Grado por defecto: el siguiente al que ya alcanzas.
    const next = s.grades.find((g) => s.points < g.threshold) ?? s.grades[s.grades.length - 1];
    setGrade(next.name);
  };

  if (failed) return <p className="mt-6 text-danger">No se pudo cargar la Galería.</p>;
  if (!sets) return <p className="mt-6 text-muted">Cargando Galería…</p>;

  const threshold = selected?.grades.find((g) => g.name === grade)?.threshold ?? 0;

  return (
    <div className="mt-6 space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="Buscar set"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar set…"
          className="w-64 rounded-lg border border-line bg-surface px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Grupo">
          {[["", "Todos"] as [string, string], ...groups].map(([slug, label]) => (
            <button
              key={slug || "all"}
              type="button"
              aria-pressed={group === slug}
              onClick={() => setGroup(slug)}
              className={`rounded-full border px-3 py-1 text-sm ${
                group === slug ? "border-accent bg-surface-2 font-medium" : "border-line text-muted hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-muted">{visible.length} sets</span>
      </div>

      <div className={`grid gap-5 ${selected ? "lg:grid-cols-[minmax(0,1fr)_32rem]" : ""}`}>
        <div
          className={`grid items-start gap-3 self-start ${
            selected ? "sm:grid-cols-2 xl:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
          }`}
        >
          {visible.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => open(s)}
              aria-pressed={selected?.id === s.id}
              className={`flex flex-col gap-3 rounded-card border bg-surface p-4 text-left transition-colors hover:border-accent/60 ${
                selected?.id === s.id ? "border-accent" : "border-line"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-bg">
                  {s.image_path ? (
                    <Badge path={s.image_path} alt={s.name} size={32} />
                  ) : (
                    <span aria-hidden>🏆</span>
                  )}
                </span>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{s.name}</p>
                  <p className="text-xs text-muted">
                    {s.required} jugadores · {s.group_name}
                  </p>
                </div>
              </div>
              <div className="flex gap-1.5" aria-label="Grados">
                {s.grades.map((g) => (
                  <span
                    key={g.name}
                    title={`${g.name}: ${formatNumber(g.threshold)} puntos`}
                    className={`grid h-6 w-6 place-items-center rounded border text-[11px] font-semibold ${
                      GRADE_CLS[g.name] ?? ""
                    } ${s.grade && s.grades.findIndex((x) => x.name === s.grade) >= s.grades.indexOf(g) ? "bg-surface-2" : "opacity-40"}`}
                  >
                    {g.name}
                  </span>
                ))}
              </div>
              <p className="text-xs text-muted">
                Coleccionados{" "}
                <span className="font-mono text-fg">
                  {Math.min(s.collected, s.required)}/{s.required}
                </span>{" "}
                · <span className="font-mono text-fg">{formatNumber(s.points)}</span> pts
              </p>
            </button>
          ))}
          {visible.length === 0 ? <p className="text-muted">Ningún set coincide.</p> : null}
        </div>

        {selected ? (
          <aside className="min-w-0 space-y-4 self-start lg:sticky lg:top-16">
            <div className="rounded-card border border-line bg-surface p-5">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-lg font-semibold">{selected.name}</h2>
                <button
                  type="button"
                  aria-label="Cerrar"
                  onClick={() => setSelected(null)}
                  className="rounded px-2 text-muted hover:text-fg"
                >
                  ✕
                </button>
              </div>
              <p className="mt-1 text-sm text-muted">
                {selected.required} jugadores · {selected.tokens} fichas en total
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Grado objetivo">
                {selected.grades.map((g) => (
                  <button
                    key={g.name}
                    type="button"
                    aria-pressed={grade === g.name}
                    onClick={() => {
                      setGrade(g.name);
                      setSolution(null);
                    }}
                    className={`rounded-lg border px-3 py-1.5 text-sm ${
                      grade === g.name ? "border-accent bg-accent/10" : "border-line"
                    }`}
                  >
                    <span className="font-semibold">{g.name}</span>{" "}
                    <span className="text-xs text-muted">{formatNumber(g.threshold)}</span>
                    {g.tokens ? <span className="ml-1 text-xs text-warn">+{g.tokens}</span> : null}
                  </button>
                ))}
              </div>
              <label className="mt-3 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={complete} onChange={(e) => setComplete(e.target.checked)} />
                Completar los {selected.required} huecos del set
              </label>
              <button
                type="button"
                disabled={solving}
                onClick={() => void solve(selected, grade, complete)}
                className="mt-3 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-60"
              >
                {solving ? "Resolviendo…" : `Resolver grado ${grade} (${formatNumber(threshold)} pts)`}
              </button>
            </div>

            {solveError ? <p className="text-danger">No se pudo resolver el set.</p> : null}
            {solution ? <SolutionView solution={solution} /> : null}
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function SolutionView({ solution }: { solution: Solution }) {
  const solved = ["optimal", "feasible", "reached"].includes(solution.status);
  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <span
        className={`rounded-full px-3 py-1 text-sm font-medium ${
          solved ? "bg-accent text-accent-fg" : "bg-danger/15 text-danger"
        }`}
      >
        {STATUS[solution.status] ?? solution.status}
      </span>
      {solved ? (
        <>
          <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
            {(
              [
                ["Puntos", formatNumber(solution.points)],
                ["Monedas necesarias", formatNumber(solution.coins_needed)],
                ["Pérdida por impuestos", formatNumber(solution.tax)],
                ["Coste total", formatNumber(solution.cost)],
                ["A comprar", String(solution.buys)],
                ["Cartas", `${solution.cards.length}/${solution.required}`],
              ] as [string, string][]
            ).map(([label, value]) => (
              <div key={label} className="rounded-lg bg-bg px-2 py-2">
                <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
                <dd className="font-mono text-sm font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          {solution.estimated ? (
            <p className="mt-3 text-xs text-warn">
              Algunas cartas usan puntos estimados (rareza o media no observadas todavía).
            </p>
          ) : null}
          <p className="mt-3 text-xs text-muted">
            Compra cada carta y véndela al instante al mismo precio: EA la marca como coleccionada.
          </p>
          <ul className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4">
            {solution.cards.map((c) => (
              <li
                key={c.resource_id}
                className={`flex flex-col rounded-lg border p-1.5 ${
                  c.collected ? "border-good/60 bg-good/10" : "border-line bg-bg"
                }`}
              >
                <CardImage path={c.image_path} position={c.positions[0]} alt={c.name ?? "Carta"} width={160} />
                <p className="mt-1 truncate text-center text-[11px] font-medium" title={c.name ?? undefined}>
                  {c.name ?? "Carta"}
                </p>
                <p className="text-center font-mono text-[11px] tabular-nums text-muted">
                  {formatNumber(c.points)}
                  {c.exact ? "" : "~"} pts
                </p>
                <p className="text-center text-[11px]">
                  {c.collected ? (
                    <span className="text-good">coleccionada</span>
                  ) : (
                    <span className="text-warn">{c.price != null ? formatNumber(c.price) : "—"}</span>
                  )}
                </p>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
