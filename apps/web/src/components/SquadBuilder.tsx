"use client";

import { useState } from "react";

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
};
type BuildResult = {
  status: string;
  formation: string;
  slots: Slot[];
  total_meta: number;
  team_rating: number;
  team_chemistry: number;
  solve_time_s: number;
  message: string | null;
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [result, setResult] = useState<BuildResult | null>(null);

  const build = async () => {
    setLoading(true);
    setError(false);
    setResult(null);
    try {
      const r = await fetch(`${apiUrl}/squad/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formation, min_chemistry: minChem }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult((await r.json()) as BuildResult);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
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
        <button
          type="button"
          onClick={build}
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
                <Stat label="Media" value={String(result.team_rating)} />
                <Stat label="Química" value={`${result.team_chemistry}/33`} />
                <Stat label="Meta total" value={result.total_meta.toFixed(1)} />
              </>
            ) : null}
          </div>
          {result.message && !solved ? (
            <p className="mt-2 text-sm text-muted">{result.message}</p>
          ) : null}
          {solved ? <Pitch slots={result.slots} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function Pitch({ slots }: { slots: Slot[] }) {
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
              <PlayerSlot key={s.slot_index} slot={s} />
            ))}
          </div>
        );
      })}
    </div>
  );
}

function PlayerSlot({ slot }: { slot: Slot }) {
  return (
    <div className="w-32 rounded-lg border border-line bg-surface p-2 text-center">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{slot.position}</span>
        <span title="Química" aria-label={`química ${slot.chemistry}`}>
          {"◆".repeat(slot.chemistry)}
          {"◇".repeat(3 - slot.chemistry)}
        </span>
      </div>
      <p className="mt-1 truncate text-sm font-medium" title={slot.name}>
        {slot.name}
      </p>
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
