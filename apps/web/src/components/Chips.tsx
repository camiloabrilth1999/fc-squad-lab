import { formatNumber } from "../lib/format";

const TIER_CLS: Record<string, string> = {
  S: "bg-sky-500/20 text-sky-300",
  "A+": "bg-emerald-500/20 text-emerald-300",
  A: "bg-green-500/20 text-green-300",
  "B+": "bg-amber-500/20 text-amber-300",
  B: "bg-orange-500/20 text-orange-300",
};

/** Precio con moneda; "—" si no hay. */
export function PriceChip({ price, label }: { price: number | null | undefined; label?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap font-mono text-[13px] font-semibold tabular-nums"
      title={label}
      aria-label={price == null ? "sin precio" : "precio"}
    >
      <span className="inline-block h-3 w-3 rounded-full bg-warn" aria-hidden />
      {price == null ? "—" : formatNumber(price)}
    </span>
  );
}

/** Meta rating con su nivel (S, A+, A, B+, B) en color. */
export function MetaChip({
  meta,
  tier,
  approx = false,
}: {
  meta: number | null | undefined;
  tier?: string | null;
  approx?: boolean;
}) {
  if (meta == null) return null;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap font-mono text-[13px] tabular-nums">
      <span className="font-semibold">
        {meta.toFixed(1)}
        {approx ? "~" : ""}
      </span>
      {tier ? (
        <span className={`rounded px-1 py-px text-[10px] font-semibold ${TIER_CLS[tier] ?? "bg-surface-2 text-muted"}`}>
          {tier}
        </span>
      ) : null}
    </span>
  );
}

/** Etiqueta pequeña de tipo/estado en una tarjeta. */
export function Tag({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "loan" | "good";
}) {
  const cls =
    tone === "loan"
      ? "bg-amber-500 text-black"
      : tone === "good"
        ? "bg-good/20 text-good"
        : "bg-surface-2 text-muted";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>{children}</span>;
}
