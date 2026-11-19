"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "../lib/format";

type Bargain = {
  resource_id: number;
  name: string | null;
  rating: number | null;
  positions: string[];
  rarity_name: string | null;
  role: string;
  meta: number;
  meta_source: "stats" | "face";
  tier: string;
  price: number;
  score: number;
};
type FodderCard = { resource_id: number; name: string | null; positions: string[]; price: number };
type FodderGroup = { rating: number; cheapest: number; cards: FodderCard[] };

const POSITIONS = ["ST", "CF", "LW", "RW", "LM", "RM", "CAM", "CM", "CDM", "LB", "RB", "LWB", "RWB", "CB", "GK"];

export default function ValueViews({ apiUrl }: { apiUrl: string }) {
  const [tab, setTab] = useState<"bargains" | "fodder">("bargains");
  return (
    <div className="mt-6 space-y-5">
      <div className="inline-flex rounded-lg border border-line p-0.5 text-sm" role="tablist">
        {(
          [
            ["bargains", "Chollos"],
            ["fodder", "Fodder para SBC"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-md px-4 py-1.5 transition-colors ${
              tab === id ? "bg-surface-2 font-medium" : "text-muted hover:text-fg"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "bargains" ? <Bargains apiUrl={apiUrl} /> : <Fodder apiUrl={apiUrl} />}
    </div>
  );
}

function Bargains({ apiUrl }: { apiUrl: string }) {
  const [position, setPosition] = useState("");
  const [minRating, setMinRating] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [applied, setApplied] = useState({ position: "", minRating: "", maxPrice: "" });
  const [items, setItems] = useState<Bargain[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    const p = new URLSearchParams({ limit: "50" });
    if (applied.position) p.set("position", applied.position);
    if (applied.minRating) p.set("min_rating", applied.minRating);
    if (applied.maxPrice) p.set("max_price", applied.maxPrice);
    fetch(`${apiUrl}/value/bargains?${p}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: { items: Bargain[] }) => {
        setItems(body.items);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, applied]);

  return (
    <section className="space-y-4">
      <p className="text-sm text-muted">
        Cartas con mucho meta para lo que cuestan: se compara el percentil de meta con el de
        precio dentro de su rol (entre cartas de 75 o más).
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setItems(null);
          setApplied({ position, minRating, maxPrice });
        }}
        className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-5"
      >
        <label className="text-sm">
          <span className="mb-1 block text-muted">Posición</span>
          <select
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="">Todas</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Media mínima</span>
          <input
            type="number"
            min={40}
            max={99}
            value={minRating}
            onChange={(e) => setMinRating(e.target.value)}
            className="w-24 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Precio máximo</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className="w-32 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong"
        >
          Buscar chollos
        </button>
      </form>
      {failed ? <p className="text-danger">No se pudieron cargar los chollos.</p> : null}
      {!items && !failed ? <p className="text-muted">Cargando…</p> : null}
      {items ? (
        items.length === 0 ? (
          <p className="text-muted">Ningún chollo con esos filtros.</p>
        ) : (
          <div className="overflow-x-auto rounded-card border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-2">Jugador</th>
                  <th className="px-2 py-2">Pos.</th>
                  <th className="px-2 py-2 text-right">Media</th>
                  <th className="px-2 py-2 text-right">Meta</th>
                  <th className="px-2 py-2 text-right">Precio</th>
                  <th className="px-4 py-2 text-right">Valor</th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.resource_id} className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-2 font-medium">
                      {b.name ?? "Carta"}
                      {b.rarity_name ? (
                        <span className="ml-2 text-xs font-normal text-muted">{b.rarity_name}</span>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 text-muted">{b.positions.slice(0, 3).join(" · ")}</td>
                    <td className="px-2 py-2 text-right font-mono tabular-nums">{b.rating ?? "–"}</td>
                    <td className="px-2 py-2 text-right font-mono tabular-nums">
                      {b.meta.toFixed(1)}
                      {b.meta_source === "face" ? "~" : ""} <span className="text-xs text-muted">{b.tier}</span>
                    </td>
                    <td className="px-2 py-2 text-right font-mono tabular-nums">{formatNumber(b.price)}</td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">+{Math.round(b.score * 100)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </section>
  );
}

function Fodder({ apiUrl }: { apiUrl: string }) {
  const [groups, setGroups] = useState<FodderGroup[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/value/fodder?min_rating=75&max_rating=92&per_rating=5`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: FodderGroup[]) => setGroups(body))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl]);

  if (failed) return <p className="text-danger">No se pudo cargar el fodder.</p>;
  if (!groups) return <p className="text-muted">Cargando…</p>;
  return (
    <section className="space-y-4">
      <p className="text-sm text-muted">
        Las cartas más baratas de cada media: el combustible para completar SBC sin pagar de más.
      </p>
      <div className="overflow-x-auto rounded-card border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-2">Media</th>
              <th className="px-2 py-2 text-right">Más barata</th>
              <th className="px-4 py-2">Las más baratas</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.rating} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2 font-mono font-semibold tabular-nums">{g.rating}</td>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{formatNumber(g.cheapest)}</td>
                <td className="px-4 py-2 text-muted">
                  {g.cards.map((c) => `${c.name ?? "Carta"} (${formatNumber(c.price)})`).join(" · ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
