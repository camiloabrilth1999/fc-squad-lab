"use client";

import { useEffect, useMemo, useState } from "react";
import { formatNumber, formatRemaining } from "../lib/format";
import CardImage from "./CardImage";
import EvolutionPlan from "./EvolutionPlan";

export { formatRemaining };

type Reward = { stat: number; name: string; count: number; max_value: number | null };
type Upgrade = { stat: number; name: string; total: number; initial: number | null };
type Level = {
  level: number;
  state: string | null;
  objectives: { id: number | null; name: string; description: string | null }[];
  awards: Reward[];
};
type Evolution = {
  id: number;
  name: string | null;
  description: string | null;
  status: string | null;
  category_id: number | null;
  category: string | null;
  timed: boolean;
  ends_at: string | null;
  gk_only: boolean;
  outfield_only: boolean;
  multi_choice: boolean;
  total_rewards: number | null;
  cost: Record<string, unknown>[];
  top_rewards: Reward[];
  upgrades: Upgrade[];
  levels: Level[];
  requirements: string[];
};

type Candidate = {
  item_id: number;
  resource_id: number;
  name: string | null;
  rating: number | null;
  positions: string[];
  eligible: boolean | null;
  unknown: string[];
  meta_before: number | null;
  meta_after: number | null;
  meta_gain: number | null;
  image_path?: string | null;
};
type Candidates = {
  items: Candidate[];
  eligible_count: number;
  unknown_count: number;
  total_checked: number;
};
type Category = { id: number; name: string; total: number; imported: number };

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: "Disponible",
  STARTED: "En curso",
  ACTIVE: "Activa",
  COMPLETE: "Completada",
  READY_FOR_REDEEM: "Lista para reclamar",
  EXPIRED: "Caducada",
  LOCKED: "Bloqueada",
};

function costLabel(c: Record<string, unknown>): string {
  // EA: {funds, finalFunds, name: "COINS" | "POINTS"}
  const amount = c.funds ?? c.amount ?? c.value ?? c.price;
  const kind = String(c.name ?? c.currency ?? c.type ?? "").toUpperCase();
  if (typeof amount === "number") {
    if (kind.includes("COIN")) return `${formatNumber(amount)} monedas`;
    if (kind.includes("POINT") || kind.includes("FC")) return `${formatNumber(amount)} FC Points`;
    return `${formatNumber(amount)} ${kind.toLowerCase()}`.trim();
  }
  return JSON.stringify(c);
}

export default function EvolutionsBrowser({ apiUrl }: { apiUrl: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const [items, setItems] = useState<Evolution[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [mine, setMine] = useState<number | null>(null);
  const [showPlan, setShowPlan] = useState(false);
  const [now, setNow] = useState(0); // «ahora» de la última carga (render puro)
  const [status, setStatus] = useState("");
  const [onlyFree, setOnlyFree] = useState(false);
  const [expiring, setExpiring] = useState(false);
  const [sort, setSort] = useState<"default" | "ends" | "name">("default");

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/evolutions/categories`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((body: unknown) => setCategories(Array.isArray(body) ? (body as Category[]) : []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl]);

  useEffect(() => {
    const ctrl = new AbortController();
    const p = new URLSearchParams({ limit: "200" });
    if (category !== null) p.set("category_id", String(category));
    if (applied.trim()) p.set("q", applied.trim());
    fetch(`${apiUrl}/evolutions?${p}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: { items: Evolution[] }) => {
        setItems(body.items);
        setNow(Date.now());
        setFailed(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, category, applied]);

  const pick = (id: number | null) => {
    setItems(null);
    setCategory(id);
  };

  const statuses = useMemo(() => {
    const count = new Map<string, number>();
    for (const e of items ?? []) if (e.status) count.set(e.status, (count.get(e.status) ?? 0) + 1);
    return [...count.entries()];
  }, [items]);

  const visible = useMemo(() => {
    const list = (items ?? []).filter(
      (e) =>
        (!status || e.status === status) &&
        (!onlyFree || e.cost.length === 0) &&
        (!expiring || (e.ends_at !== null && new Date(e.ends_at).getTime() - now < 48 * 3_600_000 && new Date(e.ends_at).getTime() > now)),
    );
    if (sort === "ends") {
      const t = (e: Evolution) => (e.ends_at ? new Date(e.ends_at).getTime() : Number.POSITIVE_INFINITY);
      list.sort((a, b) => t(a) - t(b));
    } else if (sort === "name") {
      list.sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""));
    }
    return list;
  }, [items, now, status, onlyFree, expiring, sort]);

  const pill = (active: boolean) =>
    `rounded-full border px-3 py-1 text-sm ${
      active ? "border-accent bg-surface-2 font-medium" : "border-line text-muted hover:text-fg"
    }`;

  return (
    <div className="mt-6 space-y-5">
      <div>
        <button
          type="button"
          aria-expanded={showPlan}
          onClick={() => setShowPlan((v) => !v)}
          className="rounded-lg border border-accent px-3 py-1.5 text-sm font-medium text-accent-strong hover:bg-accent/10"
        >
          {showPlan ? "Ocultar el plan" : "Plan para tu club"}
        </button>
      </div>
      {showPlan ? <EvolutionPlan apiUrl={apiUrl} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => pick(null)} aria-pressed={category === null} className={pill(category === null)}>
          Todas
        </button>
        {categories.map((c) => (
          <button key={c.id} type="button" onClick={() => pick(c.id)} aria-pressed={category === c.id} className={pill(category === c.id)}>
            {c.name}{" "}
            <span className="text-xs text-muted">
              {c.imported}/{c.total}
            </span>
          </button>
        ))}
        <form
          className="ml-auto flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setItems(null);
            setApplied(q);
          }}
        >
          <input
            aria-label="Buscar evolución"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar…"
            className="w-44 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg hover:bg-accent-strong"
          >
            Buscar
          </button>
        </form>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select
          aria-label="Estado"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-line bg-surface px-3 py-1.5"
        >
          <option value="">Todos los estados</option>
          {statuses.map(([st, n]) => (
            <option key={st} value={st}>
              {`${STATUS_LABEL[st] ?? st} (${n})`}
            </option>
          ))}
        </select>
        <button type="button" aria-pressed={onlyFree} onClick={() => setOnlyFree((v) => !v)} className={pill(onlyFree)}>
          Solo gratis
        </button>
        <button type="button" aria-pressed={expiring} onClick={() => setExpiring((v) => !v)} className={pill(expiring)}>
          Caducan pronto
        </button>
        <label className="ml-auto flex items-center gap-2 text-muted">
          Ordenar
          <select
            aria-label="Ordenar"
            value={sort}
            onChange={(e) => setSort(e.target.value as "default" | "ends" | "name")}
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-fg"
          >
            <option value="default">Orden de EA</option>
            <option value="ends">Caducan antes</option>
            <option value="name">Nombre</option>
          </select>
        </label>
      </div>

      {failed ? <p className="text-danger">No se pudieron cargar las evoluciones.</p> : null}
      {!items && !failed ? <p className="text-muted">Cargando…</p> : null}
      {items && items.length === 0 ? (
        <div className="rounded-card border border-dashed border-line bg-surface p-8 text-center text-muted">
          Aún no hay evoluciones aquí. Abre <strong>Evoluciones</strong> en la web app de EA con la
          extensión activa y se importan solas.
        </div>
      ) : null}
      {items && items.length > 0 && visible.length === 0 ? (
        <p className="text-muted">Ninguna evolución cumple esos filtros.</p>
      ) : null}

      <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((e) => {
          const remaining = formatRemaining(e.ends_at);
          const extra = Math.max(0, (e.total_rewards ?? 0) - e.top_rewards.length);
          const isOpen = open === e.id;
          return (
            <article key={e.id} className="flex flex-col rounded-card border border-line bg-surface p-4">
              <header className="flex items-start justify-between gap-2">
                <h3 className="font-semibold leading-snug">{e.name ?? "Evolución"}</h3>
                {e.category ? (
                  <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                    {e.category}
                  </span>
                ) : null}
              </header>
              <p className="mt-1 text-xs text-muted">
                {e.gk_only ? "solo porteros" : e.outfield_only ? "solo jugadores de campo" : "porteros y jugadores de campo"}
              </p>

              <BestPreview apiUrl={apiUrl} id={e.id} />

              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <dt className="text-muted">Estado</dt>
                <dd className="text-right font-medium">{e.status ? (STATUS_LABEL[e.status] ?? e.status) : "—"}</dd>
                <dt className="text-muted">Precio</dt>
                <dd className="text-right font-medium">
                  {e.cost.length > 0 ? `Coste: ${e.cost.map(costLabel).join(" + ")}` : "Gratis"}
                </dd>
                {remaining ? (
                  <>
                    <dt className="text-muted">Caduca</dt>
                    <dd className="text-right font-medium text-warn">Expira en {remaining}</dd>
                  </>
                ) : null}
              </dl>

              {e.description ? <p className="mt-3 line-clamp-2 text-sm text-muted">{e.description}</p> : null}

              {e.requirements.length > 0 ? (
                <p className="mt-3 rounded-lg bg-bg px-3 py-2 text-xs text-muted">
                  <span className="font-medium text-fg">Requisitos: </span>
                  {e.requirements.join(" · ")}
                </p>
              ) : null}

              {e.top_rewards.length > 0 ? (
                <ul className="mt-3 space-y-0.5 text-sm">
                  {e.top_rewards.map((r) => (
                    <li key={r.stat} className="flex justify-between gap-3">
                      <span>{r.name}</span>
                      <span className="font-mono tabular-nums text-good">
                        +{r.count}
                        {r.max_value ? <span className="text-xs text-muted"> (máx. {r.max_value})</span> : null}
                      </span>
                    </li>
                  ))}
                  {extra > 0 ? <li className="text-xs text-accent-strong">+{extra} más</li> : null}
                </ul>
              ) : null}

              <footer className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => setMine(mine === e.id ? null : e.id)}
                  aria-expanded={mine === e.id}
                  className="rounded-lg border border-line px-3 py-1.5 font-medium hover:border-accent/60"
                >
                  {mine === e.id ? "Ocultar mis cartas" : "Mis cartas aptas"}
                </button>
                {e.levels.length > 1 ? (
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : e.id)}
                    aria-expanded={isOpen}
                    className="ml-auto text-accent-strong hover:underline"
                  >
                    {isOpen ? "Ocultar niveles" : `Ver ${e.levels.length - 1} niveles`}
                  </button>
                ) : null}
              </footer>

              {mine === e.id ? <MyCards apiUrl={apiUrl} id={e.id} /> : null}

              {isOpen ? (
                <ol className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
                  {e.levels
                    .filter((l) => l.objectives.length > 0 || l.awards.length > 0)
                    .map((l) => (
                      <li key={l.level}>
                        <p className="font-medium">Nivel {l.level}</p>
                        {l.objectives.map((o) => (
                          <p key={o.id ?? o.name} className="text-muted">
                            {o.name}
                          </p>
                        ))}
                        {l.awards.length > 0 ? (
                          <p className="text-xs text-accent-strong">
                            {l.awards.map((a) => `${a.name} +${a.count}`).join(" · ")}
                          </p>
                        ) : null}
                      </li>
                    ))}
                </ol>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

/** Mejor carta de tu club para esta evolución, con su meta antes y después. */
function BestPreview({ apiUrl, id }: { apiUrl: string; id: number }) {
  const [best, setBest] = useState<Candidate | null>(null);
  const [count, setCount] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/evolutions/${id}/candidates?limit=1`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: Partial<Candidates> | null) => {
        const top = body?.items?.[0];
        if (top && typeof top.meta_before === "number" && typeof top.meta_after === "number") {
          setBest(top);
          setCount(body?.eligible_count ?? 0);
        }
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [apiUrl, id]);

  if (!best) return null;
  return (
    <div className="mt-3 flex items-center gap-3 rounded-lg bg-bg p-3">
      <div className="w-16 shrink-0">
        <CardImage path={best.image_path} rating={best.rating} position={best.positions[0]} alt={`Mejor carta: ${best.name ?? "jugador"}`} width={130} />
      </div>
      <div className="min-w-0 text-sm">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Tu mejor carta</p>
        <p className="truncate font-medium" title={best.name ?? undefined}>
          {best.name ?? "Carta"}
        </p>
        <p className="font-mono text-xs tabular-nums">
          meta {best.meta_before?.toFixed(1)} → {best.meta_after?.toFixed(1)}{" "}
          <span className="text-good">
            ({(best.meta_gain ?? 0) >= 0 ? "+" : ""}
            {(best.meta_gain ?? 0).toFixed(1)})
          </span>
        </p>
        <p className="text-[11px] text-muted">{count} de tus cartas son aptas</p>
      </div>
    </div>
  );
}

function MyCards({ apiUrl, id }: { apiUrl: string; id: number }) {
  const [data, setData] = useState<Candidates | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/evolutions/${id}/candidates?limit=12`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: Candidates) => setData(body))
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, id]);

  if (failed) return <p className="mt-3 text-sm text-danger">No se pudieron cargar tus cartas.</p>;
  if (!data) return <p className="mt-3 text-sm text-muted">Buscando en tu club…</p>;
  if (data.items.length === 0)
    return (
      <p className="mt-3 text-sm text-muted">
        Ninguna de tus {data.total_checked} cartas cumple los requisitos.
      </p>
    );
  return (
    <div className="mt-3 border-t border-line pt-3 text-sm">
      <p className="mb-2 text-xs text-muted">
        {data.eligible_count} aptas
        {data.unknown_count > 0 ? ` · ${data.unknown_count} sin poder comprobar` : ""} de{" "}
        {data.total_checked} cartas, por mayor meta final
      </p>
      <ul className="space-y-1">
        {data.items.map((c) => (
          <li key={c.item_id} className="flex items-center justify-between gap-3">
            <div className="w-9 shrink-0">
              <CardImage path={c.image_path} position={c.positions[0]} alt={`Carta de ${c.name ?? "jugador"}`} width={90} />
            </div>
            <span className="min-w-0 flex-1 truncate">
              {c.name ?? "Carta"}{" "}
              <span className="text-xs text-muted">
                {c.rating} · {c.positions.slice(0, 2).join("/")}
              </span>
              {c.eligible === null ? (
                <span className="ml-1 text-xs text-warn" title={c.unknown.join(", ")}>
                  ?
                </span>
              ) : null}
            </span>
            <span className="shrink-0 font-mono text-xs tabular-nums">
              {c.meta_before !== null && c.meta_after !== null ? (
                <>
                  {c.meta_before.toFixed(1)} → {c.meta_after.toFixed(1)}{" "}
                  <span className="text-accent">
                    ({(c.meta_gain ?? 0) >= 0 ? "+" : ""}
                    {(c.meta_gain ?? 0).toFixed(1)})
                  </span>
                </>
              ) : (
                <span className="text-muted">sin stats</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
