import { formatNumber } from "../lib/format";

export type PlayerCardData = {
  name: string | null;
  rating: number | null;
  positions: string[];
  rarityName?: string | null;
  resourceId?: number | null;
  price?: number | null;
  value?: number | null;
  untradeable?: boolean;
};

/** Nivel visual por media: bronce < 65, plata < 75, oro ≥ 75 (coincide con el solver). */
function level(rating: number | null): "bronze" | "silver" | "gold" {
  if (rating === null) return "gold";
  if (rating < 65) return "bronze";
  if (rating < 75) return "silver";
  return "gold";
}

const LEVEL_BAR: Record<string, string> = {
  bronze: "bg-[#a66a3a]",
  silver: "bg-[#9aa3ad]",
  gold: "bg-[#c8a84b]",
};

export default function PlayerCard({ player }: { player: PlayerCardData }) {
  const { name, rating, positions, rarityName, price, value, untradeable } = player;
  const lvl = rating === null ? "gold" : level(rating);
  return (
    <article className="group relative overflow-hidden rounded-card border border-line bg-surface transition-colors hover:border-accent/50">
      <span className={`absolute inset-x-0 top-0 h-1 ${LEVEL_BAR[lvl]}`} aria-hidden />
      <div className="flex items-center gap-3 p-3">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-surface-2 font-mono text-lg font-semibold tabular-nums">
          {rating ?? "–"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium" title={name ?? undefined}>
            {name ?? "Carta desconocida"}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {positions.slice(0, 4).map((p) => (
              <span key={p} className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
                {p}
              </span>
            ))}
            {rarityName ? <span className="text-[11px] text-muted">· {rarityName}</span> : null}
          </div>
        </div>
        <div className="shrink-0 text-right">
          {untradeable ? (
            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
              Intransferible
            </span>
          ) : price != null ? (
            <p className="font-mono text-sm tabular-nums" aria-label="precio">
              {formatNumber(price)}
            </p>
          ) : (
            <p className="text-sm text-muted">—</p>
          )}
          {value != null ? (
            <p className="mt-0.5 text-[11px] text-muted">valor {formatNumber(value)}</p>
          ) : null}
        </div>
      </div>
    </article>
  );
}
