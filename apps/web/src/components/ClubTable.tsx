"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { formatNumber, formatSeenAgo, sourceLabel } from "../lib/format";
import CardImage, { Badge } from "./CardImage";
import { MetaChip, PriceChip, Tag } from "./Chips";

const PAGE_SIZE = 50;
const STALE_DAYS = 30;
const TOKEN_KEY = "fcsl.importToken";

// localStorage puede no existir o lanzar (modo privado, cookies bloqueadas): nunca romper la tabla.
function loadToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function subscribeToken(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // sin persistencia: el token vale solo para esta visita
  }
}

type ClubRow = {
  item_id: number;
  resource_id: number;
  name: string | null;
  rating: number;
  positions: string[];
  rarity_name: string | null;
  untradeable: boolean;
  location: string | null;
  price: number | null;
  price_source: string | null;
  value: number;
  seen_at: string | null;
  loan?: boolean | null;
  loan_label?: string | null;
  image_path?: string | null;
  nation_image?: string | null;
  club_image?: string | null;
  meta?: number | null;
  meta_source?: string | null;
  tier?: string | null;
};
type ClubResponse = {
  items: ClubRow[];
  total: number;
  summary: { count: number; value: number; untradeable: number; unknown_cards: number; loans?: number };
};

const rowName = (r: ClubRow) => r.name ?? `Carta desconocida #${r.resource_id}`;

function ClubCard({ r }: { r: ClubRow }) {
  return (
    <article className="relative flex flex-col rounded-card border border-line bg-surface p-2 transition-all hover:-translate-y-0.5 hover:border-accent/60">
      <div className="mb-1 flex min-h-5 items-center gap-1">
        {r.loan ? (
          <Tag tone="loan">{r.loan_label ?? "Cedido"}</Tag>
        ) : r.untradeable ? (
          <Tag>Intransferible</Tag>
        ) : null}
      </div>
      <CardImage path={r.image_path} rating={r.rating} position={r.positions[0]} alt={rowName(r)} />
      <div className="mt-2 flex items-center justify-between gap-1 rounded-lg bg-bg px-2 py-1">
        {r.loan ? <span className="text-xs text-muted">No es tuyo</span> : <PriceChip price={r.price} />}
        <MetaChip meta={r.meta} tier={r.tier} approx={r.meta_source === "face"} />
      </div>
      <div className="mt-1.5 min-w-0">
        <p className="truncate text-xs font-medium" title={rowName(r)}>
          {rowName(r)}
        </p>
        <p className="flex items-center gap-1 text-[11px] text-muted">
          <Badge path={r.nation_image} alt="Nación" size={12} />
          <Badge path={r.club_image} alt="Club" size={12} />
          <span className="truncate">{r.positions.join(", ")}</span>
        </p>
        {!r.loan && r.price !== null && r.price_source ? (
          <p className="truncate text-[10px] text-muted">{sourceLabel(r.price_source)}</p>
        ) : null}
        <p className="text-[10px] text-muted">{formatSeenAgo(r.seen_at)}</p>
      </div>
    </article>
  );
}

const LOCATIONS = [
  { value: "", label: "Todas (sin lista de seguimiento)" },
  { value: "club", label: "Club" },
  { value: "storage", label: "Almacén SBC" },
  { value: "tradepile", label: "Lista de transferencias" },
  { value: "watchlist", label: "Lista de seguimiento" },
];
const locationLabel = (v: string | null) => LOCATIONS.find((l) => l.value === v)?.label ?? v ?? "";

const input = "rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-fg";

export default function ClubTable({ apiUrl }: { apiUrl: string }) {
  const [minRating, setMinRating] = useState("");
  const [maxRating, setMaxRating] = useState("");
  const [position, setPosition] = useState("");
  const [untradeable, setUntradeable] = useState(false);
  const [location, setLocation] = useState("");
  const [showStale, setShowStale] = useState(false);
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"cards" | "table">("cards");
  // Token guardado (vacío en el servidor) salvo que el usuario lo haya editado en esta visita.
  const storedToken = useSyncExternalStore(subscribeToken, loadToken, () => "");
  const [tokenDraft, setTokenDraft] = useState<string | null>(null);
  const token = tokenDraft ?? storedToken;
  const [forgetMsg, setForgetMsg] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [data, setData] = useState<ClubResponse | null>(null);
  const [failed, setFailed] = useState(false);

  // Cualquier cambio de filtro vuelve a la primera página.
  const setFilter = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setPage(1);
  };

  const changeToken = (value: string) => {
    setTokenDraft(value);
    saveToken(value);
  };

  const forgetStale = async () => {
    if (!token) {
      setForgetMsg("Falta el token de importación");
      return;
    }
    if (!window.confirm(`¿Borrar del club las cartas no vistas en ${STALE_DAYS} días? No se puede deshacer.`)) return;
    try {
      const res = await fetch(`${apiUrl}/club/forget`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-FCSL-Token": token },
        body: JSON.stringify({ older_than_days: STALE_DAYS }),
      });
      if (res.status === 401) {
        setForgetMsg("No se pudo olvidar: token de importación inválido");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body: { deleted: number } = await res.json();
      setForgetMsg(`Olvidadas ${formatNumber(body.deleted)} cartas`);
      setReload((n) => n + 1);
    } catch {
      setForgetMsg("No se pudo olvidar las cartas");
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (minRating) params.set("min_rating", minRating);
    if (maxRating) params.set("max_rating", maxRating);
    if (position) params.set("position", position);
    if (untradeable) params.set("untradeable", "true");
    if (location) params.set("location", location);
    if (showStale) params.set("max_age_days", "0");
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));

    fetch(`${apiUrl}/club?${params}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((body: ClubResponse) => {
        setData(body);
        setFailed(false);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setFailed(true);
      });
    return () => controller.abort();
  }, [apiUrl, minRating, maxRating, position, untradeable, location, showStale, page, reload]);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label className="flex flex-col gap-1">
          Media mín
          <input type="number" min={0} max={99} className={`${input} w-20`} value={minRating} onChange={(e) => setFilter(setMinRating)(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          Media máx
          <input type="number" min={0} max={99} className={`${input} w-20`} value={maxRating} onChange={(e) => setFilter(setMaxRating)(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          Posición
          <input type="text" className={`${input} w-20`} value={position} onChange={(e) => setFilter(setPosition)(e.target.value.toUpperCase())} />
        </label>
        <label className="flex flex-col gap-1">
          Ubicación
          <select className={input} value={location} onChange={(e) => setFilter(setLocation)(e.target.value)}>
            {LOCATIONS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-1">
          <input type="checkbox" checked={untradeable} onChange={(e) => setFilter(setUntradeable)(e.target.checked)} />
          Solo intransferibles
        </label>
        <label className="flex items-center gap-2 pb-1">
          <input type="checkbox" checked={showStale} onChange={(e) => setFilter(setShowStale)(e.target.checked)} />
          Mostrar cartas no vistas en {STALE_DAYS} días
        </label>
      </div>

      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label className="flex flex-col gap-1">
          Token de importación
          <input type="password" autoComplete="off" className={`${input} w-56`} value={token} onChange={(e) => changeToken(e.target.value)} />
        </label>
        <button type="button" className={input} onClick={forgetStale}>
          Olvidar cartas no vistas en {STALE_DAYS} días
        </button>
        {forgetMsg ? <span role="status">{forgetMsg}</span> : null}
      </div>

      {failed ? (
        <p className="text-red-600">No se pudo cargar el club</p>
      ) : !data ? (
        <p className="text-zinc-500">Cargando club…</p>
      ) : (
        <>
          <p className="text-sm">
            <span className="font-medium">{formatNumber(data.summary.count)}</span> jugadores · valor del club{" "}
            <span className="font-medium">{formatNumber(data.summary.value)}</span> monedas
            {data.summary.unknown_cards > 0 ? ` · ${formatNumber(data.summary.unknown_cards)} cartas desconocidas` : ""}
            {data.summary.loans ? ` · ${formatNumber(data.summary.loans)} cedidas (no cuentan en el valor)` : ""}
          </p>
          <div className="flex gap-2 text-sm" role="group" aria-label="Vista">
            {(["cards", "table"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                className={`${input} ${view === v ? "bg-surface-2 font-medium" : ""}`}
                onClick={() => setView(v)}
              >
                {v === "cards" ? "Cartas" : "Tabla"}
              </button>
            ))}
          </div>
          {data.items.length === 0 ? (
            <p className="text-zinc-500">
              No hay cartas. Abre la web app de EA con la extensión activa para importar tu club.
            </p>
          ) : view === "cards" ? (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7">
              {data.items.map((r) => (
                <ClubCard key={r.item_id} r={r} />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-zinc-500">
                  <tr>
                    <th className="py-1 pr-3">Nombre</th>
                    <th className="pr-3">Media</th>
                    <th className="pr-3">Posiciones</th>
                    <th className="pr-3">Rareza</th>
                    <th className="pr-3">Ubicación</th>
                    <th className="pr-3">Intransferible</th>
                    <th className="pr-3">Visto</th>
                    <th className="pr-3 text-right">Precio</th>
                    <th className="text-right">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.item_id} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="py-1 pr-3">
                        {rowName(r)}
                        {r.loan ? (
                          <span className="ml-2 rounded bg-amber-500 px-1.5 py-0.5 text-[11px] font-medium text-black">
                            {r.loan_label ?? "Cedido"}
                          </span>
                        ) : null}
                      </td>
                      <td className="pr-3">{r.rating}</td>
                      <td className="pr-3">{r.positions.join(", ")}</td>
                      <td className="pr-3">{r.rarity_name ?? ""}</td>
                      <td className="pr-3">{locationLabel(r.location)}</td>
                      <td className="pr-3">{r.untradeable ? "Sí" : "No"}</td>
                      <td className="pr-3 whitespace-nowrap">{formatSeenAgo(r.seen_at)}</td>
                      <td className="pr-3 text-right">
                        {r.price === null ? (
                          "—"
                        ) : (
                          <>
                            {formatNumber(r.price)}
                            {r.price_source ? (
                              <span className="block text-xs text-zinc-500">{sourceLabel(r.price_source)}</span>
                            ) : null}
                          </>
                        )}
                      </td>
                      <td className="text-right">{formatNumber(r.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center gap-3 text-sm">
            <button type="button" className={input} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Anterior
            </button>
            <span>
              Página {page} de {pages}
            </span>
            <button type="button" className={input} disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
              Siguiente
            </button>
          </div>
        </>
      )}
    </div>
  );
}
