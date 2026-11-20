"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber } from "../lib/format";
import CardImage from "./CardImage";

type GroupMin = { kind: string; id: number; name: string; k: number };
type Task = {
  objective_id: number;
  group: string;
  text: string;
  kind: string;
  scope_label: string;
  progress: number;
  target: number;
  remaining: number;
  matches: number;
  constraints: GroupMin[];
  notes: string[];
  unresolved: string[];
  rewards?: string[];
  value?: number;
  value_known?: boolean;
  done?: boolean;
};
type Skipped = { objective_id: number; group: string; text: string; reason: string };
type Candidates = { plannable: Task[]; skipped: Skipped[] };
type SquadSlot = {
  slot_index: number;
  position: string;
  name: string;
  rating: number;
  image_path?: string | null;
};
type Squad = {
  status: string;
  formation: string;
  team_rating: number;
  team_chemistry: number;
  slots: SquadSlot[];
};
type Session = {
  scope: string;
  label: string;
  matches: number;
  constraints: GroupMin[];
  tasks: Task[];
  value?: number;
  value_per_match?: number;
  play_matches?: number;
  play_value?: number;
};
type Plan = {
  sessions: Session[];
  dropped: Skipped[];
  skipped: Skipped[];
  totals: {
    objectives: number;
    matches: number;
    matches_separate: number;
    saved: number;
    value?: number;
    play_matches?: number;
    play_value?: number;
  };
  assumptions: Record<string, number>;
};

const KIND_LABEL: Record<string, string> = {
  league: "de la liga",
  nation: "de",
  club: "del club",
};

const minsParam = (cs: GroupMin[]) => cs.map((c) => `${c.kind}:${c.id}:${c.k}`).join(",");

export default function ObjectivesPlan({ apiUrl }: { apiUrl: string }) {
  const [cands, setCands] = useState<Candidates | null>(null);
  const [failed, setFailed] = useState(false);
  const [picked, setPicked] = useState<Set<number> | null>(null); // null = todos
  const [winRate, setWinRate] = useState("60");
  const [budget, setBudget] = useState("");
  const [sort, setSort] = useState<"value" | "matches">("value");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/objectives/plan/candidates`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((b: Candidates) => {
        setCands(b);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl]);

  const groups = useMemo(() => {
    const by = new Map<string, Task[]>();
    for (const t of cands?.plannable ?? []) by.set(t.group, [...(by.get(t.group) ?? []), t]);
    return [...by.entries()];
  }, [cands]);

  if (failed) return <p className="text-danger">No se pudieron cargar los objetivos planificables.</p>;
  if (!cands) return <p className="text-muted">Cargando…</p>;
  if (cands.plannable.length === 0)
    return (
      <p className="rounded-card border border-dashed border-line bg-surface p-8 text-center text-muted">
        No hay objetivos de partidos pendientes que planificar.
      </p>
    );

  const isOn = (id: number) => picked === null || picked.has(id);
  const toggle = (id: number) => {
    const all = new Set((picked ?? new Set(cands.plannable.map((t) => t.objective_id))).values());
    if (all.has(id)) all.delete(id);
    else all.add(id);
    setPicked(all);
  };
  const chosen = cands.plannable.filter((t) => isOn(t.objective_id)).length;

  const compute = async () => {
    setPlanning(true);
    setPlan(null);
    setPlanError(false);
    const p = new URLSearchParams({ win_rate: String((Number(winRate) || 60) / 100) });
    if (picked) p.set("ids", [...picked].join(","));
    if (budget) p.set("budget", budget);
    p.set("sort", sort);
    try {
      const r = await fetch(`${apiUrl}/objectives/plan?${p}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setPlan((await r.json()) as Plan);
    } catch {
      setPlanError(true);
    } finally {
      setPlanning(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-line bg-surface p-5">
        <p className="text-sm text-muted">
          Elige los objetivos que quieres hacer. Los de un mismo modo y con mínimos de jugadores que
          caben en un mismo once se juegan con una sola plantilla: cada partido avanza todos a la vez.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <span className="mb-1 block text-muted">Partidos que ganas (%)</span>
            <input
              inputMode="numeric"
              value={winRate}
              onChange={(e) => setWinRate(e.target.value.replace(/\D/g, ""))}
              className="w-24 rounded-lg border border-line bg-bg px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-muted">Partidos que quieres jugar</span>
            <input
              inputMode="numeric"
              value={budget}
              onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))}
              placeholder="todos"
              className="w-28 rounded-lg border border-line bg-bg px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-muted">Ordenar sesiones</span>
            <select
              aria-label="Ordenar sesiones"
              value={sort}
              onChange={(e) => setSort(e.target.value as "value" | "matches")}
              className="rounded-lg border border-line bg-bg px-3 py-2 text-sm"
            >
              <option value="value">Más valor por partido</option>
              <option value="matches">Más partidos</option>
            </select>
          </label>
          <button
            type="button"
            className="text-sm text-accent-strong hover:underline"
            onClick={() => setPicked(new Set(cands.plannable.map((t) => t.objective_id)))}
          >
            Seleccionar todos
          </button>
          <button type="button" className="text-sm text-accent-strong hover:underline" onClick={() => setPicked(new Set())}>
            Ninguno
          </button>
          <button
            type="button"
            disabled={planning || chosen === 0}
            onClick={() => void compute()}
            className="ml-auto rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg hover:bg-accent-strong disabled:opacity-60"
          >
            {planning ? "Planificando…" : `Planificar ${chosen} objetivos`}
          </button>
        </div>

        <details className="mt-4">
          <summary className="cursor-pointer text-sm font-medium">Elegir objetivos ({chosen}/{cands.plannable.length})</summary>
          <div className="mt-3 max-h-96 space-y-3 overflow-y-auto pr-2">
            {groups.map(([title, tasks]) => (
              <section key={title}>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>
                <ul className="mt-1 space-y-1">
                  {tasks.map((t) => (
                    <li key={t.objective_id}>
                      <label className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={isOn(t.objective_id)}
                          onChange={() => toggle(t.objective_id)}
                          aria-label={t.text}
                          className="mt-1"
                        />
                        <span className="min-w-0">
                          {t.text}{" "}
                          <span className="font-mono text-xs text-muted">
                            (faltan {formatNumber(t.remaining)} · ~{t.matches} partidos)
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </details>
      </div>

      {planError ? <p className="text-danger">No se pudo calcular el plan.</p> : null}
      {planning ? <p className="text-muted">Buscando la mejor forma de combinarlos…</p> : null}
      {plan ? <PlanView apiUrl={apiUrl} plan={plan} /> : null}

      {cands.skipped.length > 0 ? (
        <div className="rounded-card border border-line bg-surface p-5">
          <button
            type="button"
            aria-expanded={showSkipped}
            onClick={() => setShowSkipped((v) => !v)}
            className="text-sm font-medium text-accent-strong hover:underline"
          >
            {showSkipped ? "Ocultar" : "Ver"} los {cands.skipped.length} que no se pueden planificar
          </button>
          {showSkipped ? (
            <ul className="mt-3 space-y-1.5 text-sm">
              {cands.skipped.map((s) => (
                <li key={s.objective_id}>
                  {s.text} <span className="text-xs text-muted">— {s.reason}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PlanView({ apiUrl, plan }: { apiUrl: string; plan: Plan }) {
  const t = plan.totals;
  const unvalued = plan.sessions.reduce((n, s) => n + s.tasks.filter((x) => x.value_known === false).length, 0);
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {(
          [
            ["Partidos con el plan", formatNumber(t.matches)],
            ["Si se jugaran por separado", formatNumber(t.matches_separate)],
            ["Partidos que te ahorras", formatNumber(t.saved)],
            ["Objetivos", String(t.objectives)],
            ...(t.value ? ([["Valor de los premios", `${formatNumber(t.value)} monedas`]] as [string, string][]) : []),
            ...(t.value && t.play_matches !== undefined && t.play_matches < t.matches
              ? ([
                  ["Partidos a jugar", formatNumber(t.play_matches)],
                  ["Valor con ese presupuesto", `${formatNumber(t.play_value ?? 0)} monedas`],
                ] as [string, string][])
              : []),
          ] as [string, string][]
        ).map(([label, value]) => (
          <div key={label} className="rounded-card border border-line bg-surface px-3 py-3">
            <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {unvalued > 0 ? (
        <p className="text-xs text-warn">
          {unvalued} objetivos tienen premios que no se pueden valorar (jugadores sin precio, XP…) y cuentan 0.
        </p>
      ) : null}
      <p className="text-xs text-muted">
        Estimación: ganas el {Math.round((plan.assumptions.win_rate ?? 0.6) * 100)} % de los partidos y
        marcas ~{plan.assumptions.goals_per_match} goles por partido.
      </p>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {plan.sessions.map((s, i) => (
          <SessionCard key={`${s.scope}-${i}`} apiUrl={apiUrl} session={s} />
        ))}
      </div>
      {plan.dropped.length > 0 ? (
        <div className="rounded-card border border-warn/50 bg-surface p-4 text-sm">
          <p className="font-medium text-warn">Sin plantilla posible con tu club</p>
          <ul className="mt-1 space-y-1 text-muted">
            {plan.dropped.map((d) => (
              <li key={d.objective_id}>{d.text}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function SessionCard({ apiUrl, session }: { apiUrl: string; session: Session }) {
  const [squad, setSquad] = useState<Squad | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const showSquad = async () => {
    const next = !open;
    setOpen(next);
    if (!next || squad) return;
    setLoading(true);
    try {
      const r = await fetch(`${apiUrl}/objectives/plan/squad?mins=${encodeURIComponent(minsParam(session.constraints))}`);
      if (r.ok) setSquad((await r.json()) as Squad);
    } finally {
      setLoading(false);
    }
  };

  return (
    <article className="rounded-card border border-line bg-surface p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold leading-snug">{session.label}</h3>
          <p className="text-xs text-muted">{session.tasks.length} objetivos a la vez</p>
        </div>
        <div className="shrink-0 text-right">
          <span className="block rounded-lg bg-accent/15 px-2.5 py-1 font-mono text-sm font-semibold text-accent-strong">
            ~{session.matches} partidos
          </span>
          {session.value ? (
            <span className="mt-1 block text-xs text-muted">
              <span className="font-mono text-good">{formatNumber(session.value)}</span> monedas ·{" "}
              {formatNumber(session.value_per_match ?? 0)}/partido
            </span>
          ) : null}
        </div>
      </header>
      {session.play_matches !== undefined && session.play_matches < session.matches ? (
        <p className="mt-2 rounded-lg bg-warn/10 px-3 py-1.5 text-xs text-warn">
          Con tu presupuesto: juega {session.play_matches} de {session.matches} partidos
          {session.play_matches === 0 ? " (no merece la pena)" : ""}.
        </p>
      ) : null}

      {session.constraints.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Mínimos del once">
          {session.constraints.map((c) => (
            <span key={`${c.kind}-${c.id}`} className="rounded bg-surface-2 px-2 py-0.5 text-xs">
              mín. {c.k} {KIND_LABEL[c.kind] ?? ""} {c.name}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted">Vale cualquier once.</p>
      )}

      <ul className="mt-3 space-y-1.5 text-sm">
        {session.tasks.map((t) => (
          <li key={t.objective_id} className="flex items-baseline justify-between gap-3">
            <span className={`min-w-0 ${t.done === false ? "text-muted/50 line-through" : "text-muted"}`}>
              {t.text}
              {t.rewards && t.rewards.length > 0 ? (
                <span className="block text-xs text-accent-strong">
                  {t.rewards.join(" · ")}
                  {t.value ? ` (≈${formatNumber(t.value)})` : ""}
                </span>
              ) : null}
            </span>
            <span className="shrink-0 font-mono text-xs tabular-nums">~{t.matches}</span>
          </li>
        ))}
      </ul>

      <button
        type="button"
        aria-expanded={open}
        onClick={() => void showSquad()}
        className="mt-3 rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:border-accent/60"
      >
        {open ? "Ocultar plantilla" : "Ver plantilla"}
      </button>
      {open ? (
        <div className="mt-3">
          {loading ? <p className="text-sm text-muted">Armando el once…</p> : null}
          {squad && squad.status !== "optimal" && squad.status !== "feasible" ? (
            <p className="text-sm text-danger">No hay once posible con tu club.</p>
          ) : null}
          {squad && (squad.status === "optimal" || squad.status === "feasible") ? (
            <>
              <p className="mb-2 text-xs text-muted">
                {squad.formation} · media {squad.team_rating} · química {squad.team_chemistry}
              </p>
              <ul className="grid grid-cols-4 gap-2 sm:grid-cols-6">
                {squad.slots.map((s) => (
                  <li key={s.slot_index} className="text-center">
                    <CardImage path={s.image_path} position={s.position} alt={s.name} width={120} />
                    <p className="mt-1 truncate text-[11px]" title={s.name}>
                      {s.name}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
