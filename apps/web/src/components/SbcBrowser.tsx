"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber } from "../lib/format";
import CardImage from "./CardImage";

type Summary = {
  id: string;
  set_id: string;
  set_name: string;
  name: string;
  formation: string;
  requirements: number;
  reward: string | null;
  repeatable: boolean;
  category: string | null;
  source: string;
};

type Requirement = { kind: string; op: string; value: number };
type ChallengeDetail = {
  id: string;
  name: string;
  formation: string;
  requirements: Requirement[];
  reward: string | null;
};

type SquadSlot = {
  slot_index: number;
  position: string;
  name: string;
  rating: number;
  source: string;
  untradeable: boolean;
  price: number | null;
  image_path?: string | null;
};
type SolveResult = {
  status: string;
  pool: string;
  squad: SquadSlot[];
  cost: number;
  team_rating: number;
  team_chemistry: number;
  buys: number;
  solve_time_s: number;
  message: string | null;
};

const KIND_LABEL: Record<string, string> = {
  TEAM_RATING: "Valoración del equipo",
  PLAYER_RATING: "Valoración por jugador",
  TEAM_CHEMISTRY: "Química del equipo",
  PLAYER_CHEMISTRY: "Química por jugador",
  RARE_PLAYERS: "Jugadores raros",
  LEVEL_PLAYERS: "Jugadores por nivel",
  TAG_PLAYERS: "Jugadores con etiqueta",
  LEAGUE_PLAYERS: "Jugadores de ligas",
  NATION_PLAYERS: "Jugadores de naciones",
  CLUB_PLAYERS: "Jugadores de clubes",
  DISTINCT_LEAGUES: "Ligas distintas",
  DISTINCT_NATIONS: "Naciones distintas",
  DISTINCT_CLUBS: "Clubes distintos",
  SAME_LEAGUE: "Misma liga",
  SAME_NATION: "Misma nación",
  SAME_CLUB: "Mismo club",
};
const OP_LABEL: Record<string, string> = { min: "mín.", max: "máx.", exact: "exacto" };
const reqText = (r: Requirement) =>
  `${KIND_LABEL[r.kind] ?? r.kind}: ${OP_LABEL[r.op] ?? r.op} ${r.value}`;

const STATUS: Record<string, { label: string; cls: string }> = {
  optimal: { label: "Resuelto (óptimo)", cls: "bg-accent text-accent-fg" },
  feasible: { label: "Resuelto", cls: "bg-accent text-accent-fg" },
  infeasible: { label: "No se puede completar", cls: "bg-danger/15 text-danger" },
  unknown: { label: "Sin solución en el tiempo límite", cls: "bg-warn/15 text-warn" },
};

export default function SbcBrowser({ apiUrl }: { apiUrl: string }) {
  const [list, setList] = useState<Summary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChallengeDetail | null>(null);
  const [pool, setPool] = useState<"club" | "both">("club");
  const [solving, setSolving] = useState(false);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [solveError, setSolveError] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "repeatable" | "once">("all");

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/sbc`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: Summary[]) => {
        setList(body);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl]);

  useEffect(() => {
    if (!selected) return;
    const ctrl = new AbortController();
    fetch(`${apiUrl}/sbc/${selected}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: ChallengeDetail) => setDetail(body))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
      });
    return () => ctrl.abort();
  }, [apiUrl, selected]);

  const selectChallenge = (id: string) => {
    setSelected(id);
    setDetail(null);
    setResult(null);
    setSolveError(false);
  };

  const grouped = useMemo(() => {
    const by = new Map<string, Summary[]>();
    const q = query.trim().toLowerCase();
    for (const c of list ?? []) {
      if (filter === "repeatable" && !c.repeatable) continue;
      if (filter === "once" && c.repeatable) continue;
      if (q && !`${c.name} ${c.set_name}`.toLowerCase().includes(q)) continue;
      const arr = by.get(c.set_name);
      if (arr) arr.push(c);
      else by.set(c.set_name, [c]);
    }
    return [...by.entries()];
  }, [list, query, filter]);

  const solve = async () => {
    if (!selected) return;
    setSolving(true);
    setResult(null);
    setSolveError(false);
    try {
      const r = await fetch(`${apiUrl}/sbc/${selected}/solve?pool=${pool}`, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult((await r.json()) as SolveResult);
    } catch {
      setSolveError(true);
    } finally {
      setSolving(false);
    }
  };

  if (failed) return <p className="mt-6 text-danger">No se pudo cargar los SBC.</p>;
  if (!list) return <p className="mt-6 text-muted">Cargando SBC…</p>;

  return (
    <div className="mt-6 space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="Buscar SBC"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar SBC…"
          className="w-64 rounded-lg border border-line bg-surface px-3 py-2 text-sm"
        />
        <div className="inline-flex rounded-lg border border-line bg-surface p-0.5 text-sm" role="group" aria-label="Filtro">
          {(
            [
              ["all", "Todos"],
              ["repeatable", "Repetibles"],
              ["once", "Un solo uso"],
            ] as const
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={filter === v}
              onClick={() => setFilter(v)}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                filter === v ? "bg-surface-2 font-medium" : "text-muted hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-muted">
          {grouped.reduce((n, [, items]) => n + items.length, 0)} retos
        </span>
      </div>

      <div className={`grid gap-5 ${selected ? "lg:grid-cols-[minmax(0,1fr)_30rem]" : ""}`}>
        <div
          className={`grid items-start gap-4 self-start ${
            selected ? "md:grid-cols-2" : "md:grid-cols-2 xl:grid-cols-3"
          }`}
        >
          {grouped.length === 0 ? (
            <p className="text-muted">Ningún SBC coincide con la búsqueda.</p>
          ) : null}
          {grouped.map(([setName, items]) => (
            <section
              key={setName}
              className="flex flex-col rounded-card border border-line bg-surface p-4"
            >
              <header className="mb-3 flex items-start justify-between gap-2">
                <h2 className="font-semibold leading-snug">{setName}</h2>
                {items.some((c) => c.repeatable) ? (
                  <span className="shrink-0 rounded bg-good/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-good">
                    Repetible
                  </span>
                ) : (
                  <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                    1 uso
                  </span>
                )}
              </header>
              <ul className="space-y-1.5">
                {items.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => selectChallenge(c.id)}
                      aria-current={selected === c.id ? "true" : undefined}
                      className={`flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        selected === c.id
                          ? "border-accent bg-accent/10"
                          : "border-line bg-bg hover:border-accent/50"
                      }`}
                    >
                      <span className="min-w-0 truncate">{c.name}</span>
                      <span className="flex shrink-0 items-center gap-1.5 text-[11px] text-muted">
                        <span>{c.requirements} req.</span>
                        <span className="rounded bg-surface-2 px-1.5 py-0.5">{c.formation}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        {selected ? (
          <aside className="min-w-0 space-y-4 self-start lg:sticky lg:top-16">
            <div className="rounded-card border border-line bg-surface p-5">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">{detail?.name ?? "…"}</h2>
                <span className="rounded bg-surface-2 px-2 py-0.5 text-xs text-muted">
                  {detail?.formation}
                </span>
              </div>
              {detail?.reward ? (
                <p className="mt-1 text-sm text-muted">Recompensa: {detail.reward}</p>
              ) : null}
              <ul className="mt-3 space-y-1.5">
                {(detail?.requirements ?? []).map((r, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                    {reqText(r)}
                  </li>
                ))}
              </ul>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-lg border border-line p-0.5 text-sm">
                  {(["club", "both"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPool(p)}
                      className={`rounded-md px-3 py-1 transition-colors ${
                        pool === p ? "bg-surface-2 font-medium" : "text-muted hover:text-fg"
                      }`}
                    >
                      {p === "club" ? "Solo mi club" : "Club + mercado"}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={solve}
                  disabled={solving}
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-60"
                >
                  {solving ? "Resolviendo…" : "Resolver con mi club"}
                </button>
              </div>
            </div>

            {solveError ? <p className="text-danger">No se pudo resolver el SBC.</p> : null}
            {result ? <Result result={result} /> : null}
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function Result({ result }: { result: SolveResult }) {
  const status = STATUS[result.status] ?? { label: result.status, cls: "bg-surface-2 text-muted" };
  const solved = result.status === "optimal" || result.status === "feasible";
  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <span className={`rounded-full px-3 py-1 text-sm font-medium ${status.cls}`}>{status.label}</span>
      {solved ? (
        <dl className="mt-4 grid grid-cols-4 gap-2 text-center">
          {(
            [
              ["Media", String(result.team_rating)],
              ["Química", String(result.team_chemistry)],
              ["A comprar", String(result.buys)],
              ["Coste", formatNumber(result.cost)],
            ] as [string, string][]
          ).map(([label, value]) => (
            <div key={label} className="rounded-lg bg-bg px-2 py-2">
              <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
              <dd className="font-mono text-sm font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {result.message && !solved ? (
        <p className="mt-2 text-sm text-muted">{result.message}</p>
      ) : null}
      {solved ? (
        <ul className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {result.squad.map((s) => (
            <li key={s.slot_index} className="flex flex-col rounded-lg border border-line bg-bg p-1.5">
              <CardImage
                path={s.image_path}
                position={s.position}
                alt={s.name || "Carta"}
                width={160}
              />
              <p className="mt-1 truncate text-center text-[11px] font-medium" title={s.name}>
                {s.name || "Carta"}
              </p>
              <p className="text-center text-[10px]">
                {s.source === "market" ? (
                  <span className="text-warn">comprar {s.price ? formatNumber(s.price) : ""}</span>
                ) : (
                  <span className="text-muted">
                    {s.position} · {s.rating}
                  </span>
                )}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
