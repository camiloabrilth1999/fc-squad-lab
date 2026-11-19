"use client";

import { useState } from "react";
import { formatNumber } from "../lib/format";
import { useCatalog } from "../lib/useCatalog";
import CardImage from "./CardImage";

type Slot = {
  slot_index: number;
  position: string;
  card_id: string;
  resource_id: number;
  name: string;
  rating: number;
  meta: number;
  meta_source: "stats" | "rating";
  chemistry: number;
  in_position: boolean;
  source: "club" | "market";
  price: number | null;
  loan?: boolean;
  image_path?: string | null;
};
type BuildResult = {
  status: string;
  formation: string;
  slots: Slot[];
  total_meta: number;
  team_rating: number;
  team_chemistry: number;
  solve_time_s: number;
  spent: number;
  pending_stats: number;
  message: string | null;
};

type Marked = { id: string; name: string };

export type Pool = "club" | "both";

export type OopMode = "none" | "family" | "any";
export const OOP_LABELS: Record<OopMode, string> = {
  none: "Solo en posición",
  family: "Posiciones afines",
  any: "Cualquier posición",
};

export const FORMATIONS = [
  "442", "433", "4231", "4411", "41212", "352", "3421", "532",
  "4321", "4141", "4222", "424", "343", "3142", "5212", "451",
];

const LINES: { label: string; positions: string[] }[] = [
  { label: "Ataque", positions: ["LW", "RW", "CF", "ST"] },
  { label: "Medio", positions: ["CAM", "LM", "CM", "RM", "CDM"] },
  { label: "Defensa", positions: ["LWB", "LB", "CB", "RB", "RWB"] },
  { label: "Portería", positions: ["GK"] },
];

const SIDE_ORDER = ["LW", "LWB", "LB", "LM", "CB", "CDM", "CM", "CAM", "CF", "ST", "RM", "RB", "RWB", "RW", "GK"];
const sideRank = (p: string) => {
  const i = SIDE_ORDER.indexOf(p);
  return i === -1 ? 99 : i;
};

const STATUS: Record<string, { label: string; cls: string }> = {
  optimal: { label: "Óptimo", cls: "bg-accent text-accent-fg" },
  feasible: { label: "Resuelto", cls: "bg-accent text-accent-fg" },
  infeasible: { label: "No hay once posible con tu club", cls: "bg-danger/15 text-danger" },
  unknown: { label: "Sin solución en el tiempo límite", cls: "bg-warn/15 text-warn" },
};

export default function SquadBuilder({ apiUrl }: { apiUrl: string }) {
  const [formation, setFormation] = useState("442");
  const [minChem, setMinChem] = useState(0);
  const [oop, setOop] = useState<OopMode>("family");
  const [pool, setPool] = useState<Pool>("club");
  const [budget, setBudget] = useState(100000);
  const [league, setLeague] = useState("");
  const [nation, setNation] = useState("");
  const [includeLoans, setIncludeLoans] = useState(false);
  const leagues = useCatalog(apiUrl, "league");
  const nations = useCatalog(apiUrl, "nation");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [result, setResult] = useState<BuildResult | null>(null);
  const [pinned, setPinned] = useState<Marked[]>([]);
  const [excluded, setExcluded] = useState<Marked[]>([]);

  const build = async (lists?: { pinned?: Marked[]; excluded?: Marked[] }) => {
    const pins = lists?.pinned ?? pinned;
    const outs = lists?.excluded ?? excluded;
    setLoading(true);
    setError(false);
    setResult(null);
    try {
      const r = await fetch(`${apiUrl}/squad/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          formation,
          min_chemistry: minChem,
          out_of_position: oop,
          ...(pool === "both" ? { pool, budget } : {}),
          ...(includeLoans ? { include_loans: true } : {}),
          ...(league ? { league_ids: [Number(league)] } : {}),
          ...(nation ? { nation_ids: [Number(nation)] } : {}),
          ...(pins.length ? { include_card_ids: pins.map((m) => m.id) } : {}),
          ...(outs.length ? { exclude_card_ids: outs.map((m) => m.id) } : {}),
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult((await r.json()) as BuildResult);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const togglePin = (slot: Slot) => {
    const next = pinned.some((m) => m.id === slot.card_id)
      ? pinned.filter((m) => m.id !== slot.card_id)
      : [...pinned, { id: slot.card_id, name: slot.name }];
    setPinned(next);
    void build({ pinned: next });
  };
  const exclude = (slot: Slot) => {
    const nextPins = pinned.filter((m) => m.id !== slot.card_id);
    const next = [...excluded, { id: slot.card_id, name: slot.name }];
    setPinned(nextPins);
    setExcluded(next);
    void build({ pinned: nextPins, excluded: next });
  };
  const unexclude = (id: string) => {
    const next = excluded.filter((m) => m.id !== id);
    setExcluded(next);
    void build({ excluded: next });
  };

  const solved = result && (result.status === "optimal" || result.status === "feasible");
  const status = result ? (STATUS[result.status] ?? { label: result.status, cls: "bg-surface-2" }) : null;

  return (
    <div className="mt-6 space-y-5">
      <div className="flex flex-wrap items-end gap-4 rounded-card border border-line bg-surface p-5">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Formación</span>
          <select
            value={formation}
            onChange={(e) => setFormation(e.target.value)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="best">Mejor formación</option>
            {FORMATIONS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Química mínima</span>
          <input
            type="number"
            min={0}
            max={33}
            value={minChem}
            onChange={(e) => setMinChem(Math.min(33, Math.max(0, Number(e.target.value) || 0)))}
            className="w-24 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Cartas</span>
          <select
            value={pool}
            onChange={(e) => setPool(e.target.value as Pool)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="club">Solo mi club</option>
            <option value="both">Club + mercado</option>
          </select>
        </label>
        {pool === "both" ? (
          <label className="text-sm">
            <span className="mb-1 block text-muted">Presupuesto (monedas)</span>
            <input
              type="number"
              min={0}
              step={10000}
              value={budget}
              onChange={(e) => setBudget(Math.max(0, Number(e.target.value) || 0))}
              className="w-36 rounded-lg border border-line bg-surface-2 px-3 py-2"
            />
          </label>
        ) : null}
        <label className="text-sm">
          <span className="mb-1 block text-muted">Liga</span>
          <select
            value={league}
            onChange={(e) => setLeague(e.target.value)}
            className="w-44 rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="">Todas</option>
            {leagues.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Nación</span>
          <select
            value={nation}
            onChange={(e) => setNation(e.target.value)}
            className="w-40 rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="">Todas</option>
            {nations.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Fuera de posición</span>
          <select
            value={oop}
            onChange={(e) => setOop(e.target.value as OopMode)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            {(Object.keys(OOP_LABELS) as OopMode[]).map((m) => (
              <option key={m} value={m}>
                {OOP_LABELS[m]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={includeLoans} onChange={(e) => setIncludeLoans(e.target.checked)} />
          Incluir cesiones (Hazard, Lukaku…)
        </label>
        <button
          type="button"
          onClick={() => void build()}
          disabled={loading}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-60"
        >
          {loading ? "Calculando…" : "Armar mi mejor once"}
        </button>
      </div>

      {error ? <p className="text-danger">No se pudo armar la plantilla.</p> : null}

      {result && status ? (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-sm font-medium ${status.cls}`}>
              {status.label}
            </span>
            {solved ? (
              <>
                {formation === "best" ? <Stat label="Formación" value={result.formation} /> : null}
                <Stat label="Media" value={String(result.team_rating)} />
                <Stat label="Química" value={`${result.team_chemistry}/33`} />
                <Stat label="Meta total" value={result.total_meta.toFixed(1)} />
                {result.spent > 0 ? (
                  <Stat label="A comprar" value={`${formatNumber(result.spent)} monedas`} />
                ) : null}
              </>
            ) : null}
          </div>
          {result.message && !solved ? (
            <p className="mt-2 text-sm text-muted">{result.message}</p>
          ) : null}
          {result.pending_stats > 0 ? (
            <p className="mt-2 text-sm text-warn">
              {result.pending_stats} candidatos del mercado aún no tienen stats y no se usaron. Corre{" "}
              <code>make squad-scan</code> para bajarlos.
            </p>
          ) : null}
          {excluded.length > 0 ? (
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
              Excluidos:
              {excluded.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => unexclude(m.id)}
                  aria-label={`Quitar exclusión de ${m.name}`}
                  className="rounded bg-surface-2 px-2 py-0.5 text-xs hover:text-fg"
                >
                  {m.name} ×
                </button>
              ))}
            </p>
          ) : null}
          {solved ? (
            <Pitch
              slots={result.slots}
              pinned={pinned.map((m) => m.id)}
              onPin={togglePin}
              onExclude={exclude}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Pitch({
  slots,
  pinned,
  onPin,
  onExclude,
}: {
  slots: Slot[];
  pinned: string[];
  onPin: (s: Slot) => void;
  onExclude: (s: Slot) => void;
}) {
  return (
    <div className="mt-4 space-y-3 rounded-card bg-surface-2 p-4">
      {LINES.map((line) => {
        const row = slots
          .filter((s) => line.positions.includes(s.position))
          .sort((a, b) => sideRank(a.position) - sideRank(b.position));
        if (row.length === 0) return null;
        return (
          <div key={line.label} aria-label={line.label} className="flex flex-wrap justify-center gap-3">
            {row.map((s) => (
              <PlayerSlot
                key={s.slot_index}
                slot={s}
                pinned={pinned.includes(s.card_id)}
                onPin={() => onPin(s)}
                onExclude={() => onExclude(s)}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}

function PlayerSlot({
  slot,
  pinned,
  onPin,
  onExclude,
}: {
  slot: Slot;
  pinned: boolean;
  onPin: () => void;
  onExclude: () => void;
}) {
  return (
    <div
      className={`w-32 rounded-lg border bg-surface p-2 text-center ${
        slot.in_position ? "border-line" : "border-warn/60"
      }`}
    >
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{slot.position}</span>
        <span title="Química" aria-label={`química ${slot.chemistry}`}>
          {"◆".repeat(slot.chemistry)}
          {"◇".repeat(3 - slot.chemistry)}
        </span>
      </div>
      <div className="relative mx-auto mt-1 w-20">
        <CardImage path={slot.image_path} position={slot.position} alt={slot.name} width={160} />
        {slot.loan ? (
          <span className="absolute inset-x-0 bottom-0 rounded bg-amber-500 px-1 text-[10px] font-medium text-black">
            Cedido
          </span>
        ) : null}
      </div>
      <p className="mt-1 truncate text-sm font-medium" title={slot.name}>
        {slot.name}
      </p>
      {slot.source === "market" ? (
        <p className="text-[11px] text-warn">comprar {slot.price ? formatNumber(slot.price) : ""}</p>
      ) : null}
      {slot.in_position ? null : (
        <p className="text-[11px] text-warn">fuera de posición</p>
      )}
      <div className="mt-1 flex justify-center gap-1 text-xs">
        <button
          type="button"
          onClick={onPin}
          aria-pressed={pinned}
          aria-label={`${pinned ? "Soltar" : "Fijar"} a ${slot.name}`}
          className={`rounded px-1.5 py-0.5 ${pinned ? "bg-accent text-accent-fg" : "bg-surface-2 text-muted hover:text-fg"}`}
        >
          📌
        </button>
        <button
          type="button"
          onClick={onExclude}
          aria-label={`Excluir a ${slot.name}`}
          className="rounded bg-surface-2 px-1.5 py-0.5 text-muted hover:text-fg"
        >
          🚫
        </button>
      </div>
      <p className="font-mono text-xs tabular-nums text-muted">
        {slot.rating} ·{" "}
        <span className="text-fg" title={slot.meta_source === "stats" ? "Meta rating" : "Sin stats: rating"}>
          meta {slot.meta.toFixed(1)}
          {slot.meta_source === "rating" ? "*" : ""}
        </span>
      </p>
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
