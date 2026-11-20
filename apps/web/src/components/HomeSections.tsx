"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatRemaining } from "../lib/format";
import CardImage from "./CardImage";
import { MetaChip, PriceChip } from "./Chips";

type Tile = {
  key: string | number;
  name: string;
  position?: string;
  image_path?: string | null;
  price?: number | null;
  meta?: number | null;
  tier?: string | null;
  approx?: boolean;
};
type ClubItem = {
  item_id: number;
  name: string | null;
  positions: string[];
  image_path?: string | null;
  price: number | null;
  meta?: number | null;
  tier?: string | null;
  meta_source?: string | null;
  loan?: boolean | null;
};
type Bargain = {
  resource_id: number;
  name: string | null;
  positions: string[];
  image_path?: string | null;
  price: number;
  meta: number;
  tier: string;
  meta_source: string;
};
type Plan = { assignments: unknown[]; total_gain: number };
type Objective = { id: number; type: number; title: string | null; status: string; ends_at: string | null };

function TileGrid({ tiles }: { tiles: Tile[] }) {
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
      {tiles.map((t) => (
        <div
          key={t.key}
          className="flex flex-col rounded-card border border-line bg-surface p-2 transition-all hover:-translate-y-0.5 hover:border-accent/60"
        >
          <CardImage path={t.image_path} position={t.position} alt={t.name} width={200} />
          <div className="mt-2 flex items-center justify-between gap-1 rounded-lg bg-bg px-2 py-1">
            <PriceChip price={t.price} />
            <MetaChip meta={t.meta} tier={t.tier} approx={t.approx} />
          </div>
          <p className="mt-1 truncate text-xs text-muted" title={t.name}>
            {t.name}
          </p>
        </div>
      ))}
    </div>
  );
}

function Section({ title, href, linkLabel, children }: { title: string; href: string; linkLabel: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <Link href={href} className="rounded-lg border border-accent/50 px-3 py-1 text-xs font-medium text-accent-strong hover:bg-accent/10">
          {linkLabel} ↗
        </Link>
      </div>
      {children}
    </section>
  );
}

/** Portada: mejores cartas del club, chollos, plan de evoluciones y objetivos por caducar. */
export default function HomeSections({ apiUrl }: { apiUrl: string }) {
  const [best, setBest] = useState<Tile[] | null>(null);
  const [bargains, setBargains] = useState<Tile[] | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [objectives, setObjectives] = useState<{ count: number; soon: Objective[] } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const get = (path: string) =>
      fetch(`${apiUrl}${path}`, { signal: ctrl.signal }).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));

    get("/club?page=1&page_size=500")
      .then((b: { items: ClubItem[] }) =>
        setBest(
          b.items
            .filter((c) => !c.loan && c.meta != null)
            .sort((a, c) => (c.meta ?? 0) - (a.meta ?? 0))
            .slice(0, 7)
            .map((c) => ({
              key: c.item_id,
              name: c.name ?? "Carta",
              position: c.positions[0],
              image_path: c.image_path,
              price: c.price,
              meta: c.meta,
              tier: c.tier,
              approx: c.meta_source === "face",
            })),
        ),
      )
      .catch(() => {});
    get("/value/bargains?limit=7")
      .then((b: { items: Bargain[] }) =>
        setBargains(
          b.items.map((c) => ({
            key: c.resource_id,
            name: c.name ?? "Carta",
            position: c.positions[0],
            image_path: c.image_path,
            price: c.price,
            meta: c.meta,
            tier: c.tier,
            approx: c.meta_source === "face",
          })),
        ),
      )
      .catch(() => {});
    get("/evolutions/plan")
      .then((p: Plan) => setPlan(p))
      .catch(() => {});
    get("/objectives?status=open&limit=300")
      .then((b: { items: Objective[] }) => {
        const now = Date.now();
        const soon = b.items
          .filter((o) => o.ends_at && new Date(o.ends_at).getTime() > now)
          .sort((a, c) => new Date(a.ends_at!).getTime() - new Date(c.ends_at!).getTime())
          .slice(0, 4);
        setObjectives({ count: b.items.length, soon });
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl]);

  const soon = objectives?.soon ?? [];

  return (
    <>
      {best && best.length > 0 ? (
        <Section title="Lo mejor de tu club" href="/mi-club" linkLabel="Ver mi club">
          <TileGrid tiles={best} />
        </Section>
      ) : null}
      {bargains && bargains.length > 0 ? (
        <Section title="Chollos del mercado" href="/valor" linkLabel="Ver todos">
          <TileGrid tiles={bargains} />
        </Section>
      ) : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {plan ? (
          <Link href="/evoluciones" className="rounded-card border border-line bg-surface p-5 transition-colors hover:border-accent/60">
            <p className="text-xs uppercase tracking-wider text-muted">Plan de evoluciones</p>
            <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">
              +{plan.total_gain.toFixed(1)} <span className="text-sm font-normal text-muted">meta total</span>
            </p>
            <p className="mt-1 text-sm text-muted">{plan.assignments.length} evoluciones con tus cartas →</p>
          </Link>
        ) : null}
        {objectives ? (
          <Link href="/objetivos" className="rounded-card border border-line bg-surface p-5 transition-colors hover:border-accent/60">
            <p className="text-xs uppercase tracking-wider text-muted">Objetivos pendientes</p>
            <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{objectives.count}</p>
            {soon.length > 0 ? (
              <ul className="mt-2 space-y-0.5 text-sm text-muted">
                {soon.map((o) => (
                  <li key={`${o.type}-${o.id}`} className="flex justify-between gap-3">
                    <span className="truncate">{o.title ?? "Objetivos"}</span>
                    <span className="shrink-0 text-warn">{formatRemaining(o.ends_at)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </Link>
        ) : null}
      </div>
    </>
  );
}
