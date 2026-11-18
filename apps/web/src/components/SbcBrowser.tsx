"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber } from "../lib/format";

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
    for (const c of list ?? []) {
      const arr = by.get(c.set_name);
      if (arr) arr.push(c);
      else by.set(c.set_name, [c]);
    }
    return [...by.entries()];
  }, [list]);

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
    <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4">
        {grouped.map(([setName, items]) => (
          <section key={setName}>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              {setName}
            </h2>
            <ul className="space-y-1">
              {items.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => selectChallenge(c.id)}
                    aria-current={selected === c.id ? "true" : undefined}
                    className={`flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selected === c.id
                        ? "border-accent/60 bg-surface-2"
                        : "border-line bg-surface hover:bg-surface-2"
                    }`}
                  >
                    <span className="min-w-0 truncate">{c.name}</span>
                    <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
                      {c.formation}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </aside>

      <section className="min-w-0">
        {!selected ? (
          <div className="rounded-card border border-dashed border-line bg-surface p-8 text-center text-muted">
            Elige un reto para ver sus requisitos y resolverlo con tu club.
          </div>
        ) : (
          <div className="space-y-5">
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
              <ul className="mt-3 space-y-1">
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
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-60"
                >
                  {solving ? "Resolviendo…" : "Resolver con mi club"}
                </button>
              </div>
            </div>

            {solveError ? <p className="text-danger">No se pudo resolver el SBC.</p> : null}
            {result ? <Result result={result} /> : null}
          </div>
        )}
      </section>
    </div>
  );
}

function Result({ result }: { result: SolveResult }) {
  const status = STATUS[result.status] ?? { label: result.status, cls: "bg-surface-2 text-muted" };
  const solved = result.status === "optimal" || result.status === "feasible";
  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${status.cls}`}>
          {status.label}
        </span>
        {solved ? (
          <>
            <Stat label="Media" value={String(result.team_rating)} />
            <Stat label="Química" value={String(result.team_chemistry)} />
            <Stat label="A comprar" value={String(result.buys)} />
            <Stat label="Coste" value={`${formatNumber(result.cost)}`} />
          </>
        ) : null}
      </div>
      {result.message && !solved ? (
        <p className="mt-2 text-sm text-muted">{result.message}</p>
      ) : null}
      {solved ? (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {result.squad.map((s) => (
            <li
              key={s.slot_index}
              className="flex items-center gap-3 rounded-lg border border-line bg-surface-2 px-3 py-2"
            >
              <span className="w-10 shrink-0 text-center text-xs font-medium text-muted">
                {s.position}
              </span>
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded bg-surface font-mono text-sm tabular-nums">
                {s.rating}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm">{s.name || "Carta"}</span>
              <span className="shrink-0 text-right text-xs">
                {s.source === "market" ? (
                  <span className="text-warn">comprar {s.price ? formatNumber(s.price) : ""}</span>
                ) : (
                  <span className="text-muted">tu club</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-sm">
      <span className="text-muted">{label}:</span> <span className="font-medium">{value}</span>
    </span>
  );
}
