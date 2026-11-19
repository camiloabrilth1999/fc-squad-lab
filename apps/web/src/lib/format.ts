export const SOURCE_LABELS: Record<string, string> = {
  "ea-session": "Mercado (tu sesión)",
  "easysbc:market": "EasySBC mercado",
  "easysbc:sbc": "EasySBC SBC",
  "last-sale": "Lo que pagaste",
  "ea-min": "Mínimo EA",
};

export const sourceLabel = (source: string) => SOURCE_LABELS[source] ?? source;

const nf = new Intl.NumberFormat("es-ES", { useGrouping: "always" });

/** Formatea con separador de miles es-ES (también para 4 dígitos: 4.000). */
export const formatNumber = (n: number) => nf.format(n);

const rtf = new Intl.RelativeTimeFormat("es", { numeric: "always" });

/** "Visto hace 3 días" a partir de un ISO; "Nunca visto" si no hay fecha. */
export function formatSeenAgo(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "Nunca visto";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "Nunca visto";
  const minutes = Math.max(0, Math.floor((now - t) / 60_000));
  if (minutes < 1) return "Visto hace un momento";
  if (minutes < 60) return `Visto ${rtf.format(-minutes, "minute")}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Visto ${rtf.format(-hours, "hour")}`;
  return `Visto ${rtf.format(-Math.floor(hours / 24), "day")}`;
}

/** "1 día", "5 horas"… hasta la fecha; "caducada" si ya pasó. */
export function formatRemaining(iso: string | null, now: number = Date.now()): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now;
  if (Number.isNaN(ms)) return null;
  if (ms <= 0) return "caducada";
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return `${Math.max(1, Math.floor(ms / 60_000))} min`;
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(hours / 24)} días`;
}
