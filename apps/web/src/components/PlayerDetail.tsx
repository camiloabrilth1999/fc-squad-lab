"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "../lib/format";

type RoleMeta = { role: string; position: string; meta: number | null; source: string };
type Detail = {
  resource_id: number;
  name: string | null;
  height: number | null;
  accelerate_type: string | null;
  skill_moves: number | null;
  weak_foot: number | null;
  play_style_names: string[];
  play_style_plus_names: string[];
  league_name: string | null;
  nation_name: string | null;
  club_name: string | null;
  face_stats: Record<string, number>;
  stats: Record<string, number>;
  roles: RoleMeta[];
  price: number | null;
};

const ROLE_LABEL: Record<string, string> = {
  adv_forward: "Delantero",
  winger: "Extremo",
  playmaker: "Mediapunta",
  central_mid: "Centrocampista",
  box_crasher: "Pivote",
  falseback: "Lateral",
  defender: "Central",
  goalkeeper: "Portero",
};
const FACE: [string, string][] = [
  ["pace", "RIT"],
  ["shooting", "TIR"],
  ["passing", "PAS"],
  ["dribbling", "REG"],
  ["defending", "DEF"],
  ["physicality", "FIS"],
];
const FACE_GK: [string, string][] = [
  ["gk_diving", "estirada"],
  ["gk_handling", "paradas"],
  ["gk_kicking", "saque"],
  ["gk_reflexes", "reflejos"],
  ["gk_positioning", "colocación"],
  ["gk_speed", "velocidad"],
];

export default function PlayerDetail({ apiUrl, id }: { apiUrl: string; id: number }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${apiUrl}/players/${id}`, { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((body: Detail) => setDetail(body))
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setFailed(true);
      });
    return () => ctrl.abort();
  }, [apiUrl, id]);

  if (failed) return <p className="text-danger">No se pudo cargar el detalle.</p>;
  if (!detail) return <p className="text-muted">Cargando detalle…</p>;

  const isGk = detail.roles.some((r) => r.role === "goalkeeper");
  const face = (isGk ? FACE_GK : FACE).filter(([k]) => detail.face_stats[k] != null);
  const detailed = Object.entries(detail.stats).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid gap-5 text-sm md:grid-cols-3" aria-label={`Detalle de ${detail.name ?? "carta"}`}>
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Meta por rol</h3>
        <ul className="space-y-1">
          {detail.roles.map((r) => (
            <li key={r.role} className="flex items-center justify-between gap-3">
              <span>
                {ROLE_LABEL[r.role] ?? r.role} <span className="text-muted">({r.position})</span>
              </span>
              <span className="font-mono tabular-nums">
                {r.meta != null ? r.meta.toFixed(1) : "—"}
                {r.source === "face" ? "~" : ""}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-muted">
          {[detail.club_name, detail.league_name, detail.nation_name].filter(Boolean).join(" · ")}
        </p>
        {detail.price != null ? (
          <p className="mt-1">Precio: {formatNumber(detail.price)}</p>
        ) : null}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Cara</h3>
        <ul className="grid grid-cols-3 gap-2">
          {face.map(([k, label]) => (
            <li key={k} className="rounded bg-surface-2 px-2 py-1 text-center">
              <span className="block text-[11px] text-muted">{label}</span>
              <span className="font-mono tabular-nums">{detail.face_stats[k]}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-muted">
          {[
            detail.height ? `${detail.height} cm` : null,
            detail.skill_moves ? `${detail.skill_moves}★ filigranas` : null,
            detail.weak_foot ? `${detail.weak_foot}★ pie malo` : null,
            detail.accelerate_type ? detail.accelerate_type.toLowerCase() : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {detail.play_style_plus_names.length + detail.play_style_names.length > 0 ? (
          <p className="mt-2">
            {detail.play_style_plus_names.map((n) => (
              <span key={n} className="mr-1.5 rounded bg-accent px-1.5 py-0.5 text-xs text-accent-fg">
                {n}+
              </span>
            ))}
            {detail.play_style_names.map((n) => (
              <span key={n} className="mr-1.5 rounded bg-surface-2 px-1.5 py-0.5 text-xs">
                {n}
              </span>
            ))}
          </p>
        ) : null}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
          Stats detallados
        </h3>
        {detailed.length === 0 ? (
          <p className="text-muted">Aún no los tenemos (el meta se estima con la cara).</p>
        ) : (
          <ul className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            {detailed.map(([k, v]) => (
              <li key={k} className="flex justify-between">
                <span className="text-muted">{k.replaceAll("_", " ")}</span>
                <span className="font-mono tabular-nums">{v}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
