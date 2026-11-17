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
