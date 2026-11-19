"use client";

import { Fragment, useEffect, useState } from "react";
import { formatNumber } from "../lib/format";
import PlayerDetail from "./PlayerDetail";
import { useCatalog } from "../lib/useCatalog";

type Player = {
  resource_id: number;
  name: string | null;
  rating: number | null;
  positions: string[];
  league_name: string | null;
  nation_name: string | null;
  club_name: string | null;
  rarity_name: string | null;
  meta: number;
  role: string;
  meta_source: "stats" | "face";
  tier: string;
  price: number | null;
};
type Page = { items: Player[]; total: number; page: number; page_size: number };

export const POSITIONS = [
  "ST", "CF", "LW", "RW", "LM", "RM", "CAM", "CM", "CDM", "LB", "RB", "LWB", "RWB", "CB", "GK",
];
const TIERS = ["S", "A+", "A", "B+", "B"];
const SORTS: Record<string, string> = {
  meta: "Meta",
  rating: "Media",
  price: "Precio",
  name: "Nombre",
};
const PAGE_SIZE = 50;

const TIER_CLS: Record<string, string> = {
  S: "bg-accent text-accent-fg",
  "A+": "bg-accent/70 text-accent-fg",
  A: "bg-surface-2 text-fg",
  "B+": "bg-surface-2 text-muted",
  B: "bg-surface-2 text-muted",
};

type Filters = {
  q: string;
  position: string;
  tier: string;
  league: string;
  nation: string;
  minRating: string;
  maxPrice: string;
  sort: string;
  order: "asc" | "desc";
};
const EMPTY: Filters = {
  q: "",
  position: "",
  tier: "",
  league: "",
  nation: "",
  minRating: "",
  maxPrice: "",
  sort: "meta",
  order: "desc",
};

function query(f: Filters, page: number): string {
  const p = new URLSearchParams({ sort: f.sort, order: f.order, page: String(page), page_size: String(PAGE_SIZE) });
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.position) p.set("position", f.position);
  if (f.tier) p.set("tier", f.tier);
  if (f.league) p.set("league_id", f.league);
  if (f.nation) p.set("nation_id", f.nation);
  if (f.minRating) p.set("min_rating", f.minRating);
  if (f.maxPrice) p.set("max_price", f.maxPrice);
  return p.toString();
}

export default function PlayersBrowser({ apiUrl }: { apiUrl: string }) {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [failed, setFailed] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const leagues = useCatalog(apiUrl, "league");
  const nations = useCatalog(apiUrl, "nation");

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/players?${query(applied, page)}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: Page) => {
        setData(body);
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, applied, page]);

  const search = () => {
    setPage(1);
    setApplied(draft);
  };
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="mt-6 space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
        className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-5"
      >
        <label className="text-sm">
          <span className="mb-1 block text-muted">Nombre</span>
          <input
            value={draft.q}
            onChange={(e) => set("q", e.target.value)}
            className="w-44 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Posición</span>
          <select
            value={draft.position}
            onChange={(e) => set("position", e.target.value)}
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
          <span className="mb-1 block text-muted">Tier</span>
          <select
            value={draft.tier}
            onChange={(e) => set("tier", e.target.value)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="">Todos</option>
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Liga</span>
          <select
            value={draft.league}
            onChange={(e) => set("league", e.target.value)}
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
            value={draft.nation}
            onChange={(e) => set("nation", e.target.value)}
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
          <span className="mb-1 block text-muted">Media mínima</span>
          <input
            type="number"
            min={40}
            max={99}
            value={draft.minRating}
            onChange={(e) => set("minRating", e.target.value)}
            className="w-24 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Precio máximo</span>
          <input
            type="number"
            min={0}
            step={1000}
            value={draft.maxPrice}
            onChange={(e) => set("maxPrice", e.target.value)}
            className="w-32 rounded-lg border border-line bg-surface-2 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Ordenar por</span>
          <select
            value={draft.sort}
            onChange={(e) => set("sort", e.target.value)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            {Object.entries(SORTS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted">Orden</span>
          <select
            value={draft.order}
            onChange={(e) => set("order", e.target.value as "asc" | "desc")}
            className="rounded-lg border border-line bg-surface-2 px-3 py-2"
          >
            <option value="desc">Mayor primero</option>
            <option value="asc">Menor primero</option>
          </select>
        </label>
        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong"
        >
          Buscar
        </button>
      </form>

      {failed ? <p className="text-danger">No se pudo cargar la lista de jugadores.</p> : null}
      {!data && !failed ? <p className="text-muted">Cargando jugadores…</p> : null}

      {data ? (
        <div className="rounded-card border border-line bg-surface">
          <div className="flex items-center justify-between px-4 py-3 text-sm text-muted">
            <span>{formatNumber(data.total)} jugadores</span>
            <span>
              Página {data.page} de {pages}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-y border-line text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-2">Jugador</th>
                  <th className="px-2 py-2">Pos.</th>
                  <th className="px-2 py-2 text-right">Media</th>
                  <th className="px-2 py-2 text-right">Meta</th>
                  <th className="px-2 py-2">Tier</th>
                  <th className="px-4 py-2 text-right">Precio</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <Fragment key={p.resource_id}>
                  <tr className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-2">
                      <button
                        type="button"
                        aria-expanded={openId === p.resource_id}
                        onClick={() => setOpenId(openId === p.resource_id ? null : p.resource_id)}
                        className="font-medium hover:underline"
                      >
                        {p.name ?? "Carta"}
                      </button>
                      {p.rarity_name ? (
                        <span className="ml-2 text-xs text-muted">{p.rarity_name}</span>
                      ) : null}
                      <span className="block text-xs text-muted">
                        {[p.club_name, p.league_name, p.nation_name].filter(Boolean).join(" · ")}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-muted">{p.positions.slice(0, 3).join(" · ")}</td>
                    <td className="px-2 py-2 text-right font-mono tabular-nums">{p.rating ?? "–"}</td>
                    <td
                      className="px-2 py-2 text-right font-mono tabular-nums"
                      title={p.meta_source === "stats" ? "Meta con stats detallados" : "Meta estimado con la cara"}
                    >
                      {p.meta.toFixed(1)}
                      {p.meta_source === "face" ? "~" : ""}
                    </td>
                    <td className="px-2 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-xs ${TIER_CLS[p.tier] ?? ""}`}>
                        {p.tier}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">
                      {p.price != null ? formatNumber(p.price) : "—"}
                    </td>
                  </tr>
                  {openId === p.resource_id ? (
                    <tr className="border-b border-line/60 bg-surface-2/40">
                      <td colSpan={6} className="px-4 py-4">
                        <PlayerDetail apiUrl={apiUrl} id={p.resource_id} />
                      </td>
                    </tr>
                  ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between px-4 py-3">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((n) => Math.max(1, n - 1))}
              className="rounded-lg border border-line px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={page >= pages}
              onClick={() => setPage((n) => n + 1)}
              className="rounded-lg border border-line px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Siguiente
            </button>
          </div>
        </div>
      ) : null}
      <p className="text-xs text-muted">
        Meta con «~» = estimado con los stats de la cara; sin «~», con stats detallados.
      </p>
    </div>
  );
}
