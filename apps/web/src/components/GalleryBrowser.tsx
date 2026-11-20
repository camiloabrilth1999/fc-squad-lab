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

type PlanItem = {
  set_id: number;
  name: string;
  image_path?: string | null;
  from_grade: string | null;
  grade: string;
  tokens: number;
  points: number;
  cost: number;
  tax: number;
  buys: number;
  coins_needed: number;
};
type Plan = {
  status: string;
  tokens: number;
  tax: number;
  cost: number;
  transfers: number;
  coins_needed: number;
  sets: number;
  max_tokens: number;
  saved_tax?: number;
  items: PlanItem[];
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
  const [view, setView] = useState<"sets" | "plan">("sets");
  const [limits, setLimits] = useState({ target: "", coins: "", tax: "", transfers: "", sets: "" });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState(false);

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

  const [pool, setPool] = useState<SolCard[] | null>(null);
  const [poolQuery, setPoolQuery] = useState("");
  const [poolOpen, setPoolOpen] = useState(false);

  const loadPool = async (id: number, q: string) => {
    try {
      const r = await fetch(`${apiUrl}/gallery/${id}/cards?q=${encodeURIComponent(q)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setPool(((await r.json()) as { cards: SolCard[] }).cards);
    } catch {
      setPool([]);
    }
  };

  /** Marca o desmarca cartas a mano y refresca progreso, solución y listado. */
  const mark = async (ids: number[], collected: boolean) => {
    if (ids.length === 0) return;
    try {
      const r = await fetch(`${apiUrl}/gallery/collected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resource_ids: ids, collected }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch {
      setSolveError(true);
      return;
    }
    const fresh = await fetch(`${apiUrl}/gallery`)
      .then((x) => (x.ok ? x.json() : null))
      .catch(() => null);
    if (fresh) {
      setSets(fresh.items);
      setSelected((cur) => (cur ? (fresh.items as GallerySet[]).find((x) => x.id === cur.id) ?? cur : cur));
    }
    if (selected) {
      if (solution) await solve(selected, grade, complete);
      if (poolOpen) await loadPool(selected.id, poolQuery);
    }
  };

  const computePlan = async () => {
    setPlanning(true);
    setPlan(null);
    setPlanError(false);
    const p = new URLSearchParams({ complete: String(complete) });
    if (limits.target) p.set("target_tokens", limits.target);
    if (limits.coins) p.set("max_coins", limits.coins);
    if (limits.tax) p.set("max_tax", limits.tax);
    if (limits.transfers) p.set("max_transfers", limits.transfers);
    if (limits.sets) p.set("max_sets", limits.sets);
    try {
      const r = await fetch(`${apiUrl}/gallery/plan?${p}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setPlan((await r.json()) as Plan);
    } catch {
      setPlanError(true);
    } finally {
      setPlanning(false);
    }
  };

  const openPlanItem = (it: PlanItem) => {
    const s = (sets ?? []).find((x) => x.id === it.set_id);
    if (!s) return;
    setSelected(s);
    setGrade(it.grade);
    void solve(s, it.grade, complete);
  };

  const open = (s: GallerySet) => {
    setSelected(s);
    setPool(null);
    setPoolOpen(false);
    setPoolQuery("");
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
      <div className="inline-flex rounded-lg border border-line bg-surface p-0.5 text-sm" role="group" aria-label="Vista">
        {(
          [
            ["sets", "Sets"],
            ["plan", "Plan de fichas"],
          ] as const
        ).map(([v, label]) => (
          <button
            key={v}
            type="button"
            aria-pressed={view === v}
            onClick={() => setView(v)}
            className={`rounded-md px-4 py-1.5 transition-colors ${
              view === v ? "bg-accent font-medium text-accent-fg" : "text-muted hover:text-fg"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {view === "plan" ? (
        <PlanForm
          limits={limits}
          setLimits={setLimits}
          onCompute={() => void computePlan()}
          loading={planning}
        />
      ) : null}
      {planError ? <p className="text-danger">No se pudo calcular el plan.</p> : null}

      {view === "sets" ? (
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
      ) : null}

      <div className={`grid gap-5 ${selected ? "lg:grid-cols-[minmax(0,1fr)_32rem]" : ""}`}>
        {view === "plan" ? (
          <PlanView plan={plan} loading={planning} selectedId={selected?.id ?? null} onOpen={openPlanItem} />
        ) : (
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
        )}

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
            {solution ? <SolutionView solution={solution} onMark={mark} /> : null}
            <div className="rounded-card border border-line bg-surface p-5">
              <button
                type="button"
                aria-expanded={poolOpen}
                onClick={() => {
                  const next = !poolOpen;
                  setPoolOpen(next);
                  if (next && pool === null) void loadPool(selected.id, poolQuery);
                }}
                className="text-sm font-medium text-accent-strong hover:underline"
              >
                {poolOpen ? "Ocultar cartas del set" : "Ver y marcar las cartas del set"}
              </button>
              {poolOpen ? (
                <div className="mt-3 space-y-3">
                  <input
                    aria-label="Buscar carta del set"
                    value={poolQuery}
                    onChange={(e) => {
                      setPoolQuery(e.target.value);
                      void loadPool(selected.id, e.target.value);
                    }}
                    placeholder="Buscar jugador…"
                    className="w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm"
                  />
                  {pool === null ? <p className="text-sm text-muted">Cargando…</p> : null}
                  {pool && pool.length === 0 ? <p className="text-sm text-muted">Sin resultados.</p> : null}
                  <CardGrid cards={pool ?? []} onMark={mark} />
                </div>
              ) : null}
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function SolutionView({
  solution,
  onMark,
}: {
  solution: Solution;
  onMark: (ids: number[], collected: boolean) => void;
}) {
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
          {solution.buys > 0 ? (
            <button
              type="button"
              onClick={() => onMark(solution.cards.filter((c) => !c.collected).map((c) => c.resource_id), true)}
              className="mt-3 rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent/60"
            >
              Ya las compré: marcar las {solution.buys} como coleccionadas
            </button>
          ) : null}
          <CardGrid cards={solution.cards} onMark={onMark} />
        </>
      ) : null}
    </div>
  );
}

const field = "w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm";

function PlanForm({
  limits,
  setLimits,
  onCompute,
  loading,
}: {
  limits: { target: string; coins: string; tax: string; transfers: string; sets: string };
  setLimits: (l: { target: string; coins: string; tax: string; transfers: string; sets: string }) => void;
  onCompute: () => void;
  loading: boolean;
}) {
  const set = (k: keyof typeof limits) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setLimits({ ...limits, [k]: e.target.value.replace(/[^\d]/g, "") });
  const inputs: [keyof typeof limits, string, string][] = [
    ["target", "Objetivo de fichas", "p. ej. 750"],
    ["coins", "Saldo de monedas", "sin límite"],
    ["tax", "Impuestos máx.", "sin límite"],
    ["transfers", "Traspasos máx.", "sin límite"],
    ["sets", "Sets máx.", "sin límite"],
  ];
  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <p className="mb-3 text-sm text-muted">
        Con un objetivo de fichas, el plan de menor pérdida por impuestos. Sin objetivo, el que más
        fichas da dentro de tus límites.
      </p>
      <div className="grid grid-cols-2 items-end gap-3 md:grid-cols-6">
        {inputs.map(([key, label, ph]) => (
          <label key={key} className="text-sm">
            <span className="mb-1 block text-muted">{label}</span>
            <input
              inputMode="numeric"
              value={limits[key]}
              onChange={set(key)}
              placeholder={ph}
              className={field}
            />
          </label>
        ))}
        <button
          type="button"
          disabled={loading}
          onClick={onCompute}
          className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-60"
        >
          {loading ? "Calculando…" : "Calcular plan"}
        </button>
      </div>
    </div>
  );
}

function PlanView({
  plan,
  loading,
  selectedId,
  onOpen,
}: {
  plan: Plan | null;
  loading: boolean;
  selectedId: number | null;
  onOpen: (it: PlanItem) => void;
}) {
  if (loading) return <p className="text-muted">Calculando el plan de todos los sets…</p>;
  if (!plan) return <p className="text-muted">Indica tus límites y pulsa «Calcular plan».</p>;
  if (plan.status === "infeasible" || plan.status === "unknown") {
    return (
      <div className="rounded-card border border-line bg-surface p-5 text-sm">
        <p className="font-medium text-danger">
          {plan.status === "unknown" ? "Sin solución en el tiempo límite." : "Ese objetivo no es alcanzable con tus límites."}
        </p>
        {plan.status === "infeasible" ? (
          <p className="mt-1 text-muted">Lo máximo con esos límites son {formatNumber(plan.max_tokens)} fichas.</p>
        ) : null}
      </div>
    );
  }
  return (
    <div className="min-w-0 space-y-4 self-start">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {(
          [
            ["Fichas", formatNumber(plan.tokens)],
            ["Monedas necesarias", formatNumber(plan.coins_needed)],
            ["Pérdida por impuestos", formatNumber(plan.tax)],
            ["Traspasos", formatNumber(plan.transfers)],
            ["Sets", String(plan.sets)],
          ] as [string, string][]
        ).map(([label, value]) => (
          <div key={label} className="rounded-card border border-line bg-surface px-3 py-3">
            <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted">
        Las cartas que están en varios sets (por ejemplo club y liga) se compran una sola vez.
        {plan.saved_tax ? (
          <>
            {" "}
            Ahorro por reutilizarlas:{" "}
            <span className="font-mono text-good">{formatNumber(plan.saved_tax)}</span> de impuestos.
          </>
        ) : null}
      </p>
      <div className="grid items-start gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {plan.items.map((it) => (
          <button
            key={it.set_id}
            type="button"
            onClick={() => onOpen(it)}
            aria-pressed={selectedId === it.set_id}
            className={`flex flex-col gap-2 rounded-card border bg-surface p-4 text-left transition-colors hover:border-accent/60 ${
              selectedId === it.set_id ? "border-accent" : "border-line"
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-bg">
                {it.image_path ? <Badge path={it.image_path} alt={it.name} size={32} /> : <span aria-hidden>🏆</span>}
              </span>
              <p className="min-w-0 flex-1 truncate font-semibold">{it.name}</p>
              <span
                className={`grid h-7 min-w-7 place-items-center rounded border px-1 text-sm font-semibold ${
                  GRADE_CLS[it.grade] ?? ""
                }`}
              >
                {it.grade}
              </span>
            </div>
            <p className="text-xs text-muted">
              <span className="font-mono text-fg">+{it.tokens}</span> fichas ·{" "}
              <span className="font-mono text-fg">{formatNumber(it.tax)}</span> impuestos ·{" "}
              {it.buys} traspasos
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}

function CardGrid({
  cards,
  onMark,
}: {
  cards: SolCard[];
  onMark: (ids: number[], collected: boolean) => void;
}) {
  return (
    <ul className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4">
      {cards.map((c) => (
        <li key={c.resource_id}>
          <button
            type="button"
            aria-pressed={c.collected}
            aria-label={`${c.collected ? "Desmarcar" : "Marcar como coleccionada"} a ${c.name ?? "carta"}`}
            onClick={() => onMark([c.resource_id], !c.collected)}
            className={`flex w-full flex-col rounded-lg border p-1.5 text-left transition-colors hover:border-accent/60 ${
              c.collected ? "border-good/60 bg-good/10" : "border-line bg-bg"
            }`}
          >
            <CardImage path={c.image_path} position={c.positions[0]} alt={c.name ?? "Carta"} width={160} />
            <span className="mt-1 block truncate text-center text-[11px] font-medium" title={c.name ?? undefined}>
              {c.name ?? "Carta"}
            </span>
            <span className="block text-center font-mono text-[11px] tabular-nums text-muted">
              {formatNumber(c.points)}
              {c.exact ? "" : "~"} pts
            </span>
            <span className="block text-center text-[11px]">
              {c.collected ? (
                <span className="text-good">coleccionada ✓</span>
              ) : (
                <span className="text-warn">{c.price != null ? formatNumber(c.price) : "—"}</span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
