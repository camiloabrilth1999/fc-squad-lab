"use client";

import { useEffect, useState } from "react";

export type CatalogEntry = { id: number; name: string };
export type CatalogKind = "league" | "nation" | "club";

/** Lista de ligas, naciones o clubes (id + nombre) desde la API; vacía si falla. */
export function useCatalog(apiUrl: string, kind: CatalogKind): CatalogEntry[] {
  const [items, setItems] = useState<CatalogEntry[]>([]);
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/catalog?kind=${kind}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((body: unknown) => setItems(Array.isArray(body) ? (body as CatalogEntry[]) : []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl, kind]);
  return items;
}
