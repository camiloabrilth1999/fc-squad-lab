"use client";

import { useEffect, useState } from "react";
import { formatNumber, sourceLabel } from "../lib/format";

type Sync = { status: string; finished_at: string | null; items: number; error: string | null };
type Status = {
  cards: number;
  prices: Record<string, number>;
  club_items: number;
  last_sync: Record<string, Sync>;
};

const KIND_LABELS: Record<string, string> = {
  club: "Club",
  prices: "Precios",
  market: "Mercado",
};

const SYNC_KINDS = ["club", "prices", "market"];

function formatDate(iso: string | null) {
  if (!iso) return "Nunca";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("es-ES");
}

export default function DataStatus({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<Status | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiUrl}/data/status`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((body: Status) => setData(body))
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setFailed(true);
      });
    return () => controller.abort();
  }, [apiUrl]);

  if (failed) {
    return <p className="text-sm text-red-600">No se pudo cargar el estado de los datos</p>;
  }
  if (!data) return <p className="text-sm text-zinc-500">Cargando estado…</p>;

  const kinds = [...new Set([...SYNC_KINDS, ...Object.keys(data.last_sync)])];
  const prices = Object.entries(data.prices);

  return (
    <section aria-label="Estado de los datos" className="rounded border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1">
        <dt className="text-zinc-500">Cartas conocidas</dt>
        <dd>{formatNumber(data.cards)}</dd>
        <dt className="text-zinc-500">Ítems del club</dt>
        <dd>{formatNumber(data.club_items)}</dd>
      </dl>
      <h3 className="mt-3 font-medium">Precios por fuente</h3>
      {prices.length === 0 ? (
        <p className="text-zinc-500">Sin precios</p>
      ) : (
        <ul>
          {prices.map(([source, n]) => (
            <li key={source}>
              <span>{sourceLabel(source)}</span>: {formatNumber(n)}
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-3 font-medium">Última sincronización</h3>
      <ul>
        {kinds.map((kind) => {
          const s = data.last_sync[kind];
          return (
            <li key={kind}>
              {KIND_LABELS[kind] ?? kind}: <span>{s ? formatDate(s.finished_at) : "Nunca"}</span>
              {s && s.status !== "ok" ? ` (${s.status})` : ""}
              {s?.error ? <span className="ml-2 text-red-600">{s.error}</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
