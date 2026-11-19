export type Location = "club" | "storage" | "tradepile" | "watchlist";
export type Endpoint = Location | "market" | "academy" | "objectives";

export interface EaItem {
  id: number;
  resourceId: number;
  assetId: number;
  rating: number;
  untradeable?: boolean;
  lastSalePrice?: number | null;
  marketDataMinPrice?: number | null;
  marketDataMaxPrice?: number | null;
  owners?: number | null;
  loans?: number | null;
  itemType?: string | null;
}

export interface ImportClubBody {
  location: Location;
  items: EaItem[];
  duplicate_item_ids: number[];
  /** La respuesta trae la ubicación entera: lo que no esté en ella ya no es tuyo. */
  complete: boolean;
}

export interface MarketObservation {
  resourceId: number;
  buyNowPrice: number;
  seenAt: string;
}

/** Evoluciones (EA `academy/hub/v2`) reducidas: sin el jugador de muestra ni imágenes. */
export interface EvolutionLevel {
  level: number;
  state: string | null;
  objectives: { id: number | null; name: string; description: string | null }[];
  awards: { stat: number; count: number; max_value: number | null }[];
}
export interface EvolutionSlot {
  id: number;
  content_id: number | null;
  name: string | null;
  description: string | null;
  status: string | null;
  timed: boolean;
  end_time: number | null;
  category_id: number | null;
  gk_only: boolean;
  outfield_only: boolean;
  multi_choice: boolean;
  reset_count: number;
  total_rewards: number | null;
  currencies: unknown[];
  top_rewards: { stat: number; count: number; max_value: number | null }[];
  requirements: { type: string; key: number; slot: number; value: number }[];
  levels: EvolutionLevel[];
  /** Mejora acumulada por nivel sobre un jugador de ejemplo: nivel → [{stat, total, initial}]. */
  bonuses: Record<string, { stat: number; total: number; initial: number | null }[]>;
}
export interface EvolutionsImport {
  categories: { id: number; name: string; slot_ids: number[] }[];
  slots: EvolutionSlot[];
}

/** Objetivos (EA `scmp/objective/categories/all`) reducidos: sin imágenes ni datos de jugador. */
export interface ObjectiveAward {
  type: string;
  value: number;
  count: number;
  untradeable: boolean;
  /** Solo en recompensas de tipo jugador: qué carta es. */
  item: { resource_id: number; rating: number | null } | null;
}
export interface ObjectiveTask {
  id: number;
  name: string;
  description: string | null;
  progress: number | null;
  target: number | null;
  state: string | null;
  awards: ObjectiveAward[];
}
export interface ObjectiveGroup {
  id: number;
  type: number;
  content_id: number | null;
  title: string | null;
  subtitle: string | null;
  state: number | null;
  repeatability: string | null;
  times_completed: number;
  start_time: number | null;
  end_time: number | null;
  visibility_time: number | null;
  priority: number | null;
  awards: ObjectiveAward[];
  objectives: ObjectiveTask[];
}
export interface ObjectiveCategory {
  id: number;
  name: string;
  type: number | null;
  priority: number | null;
  groups: ObjectiveGroup[];
}
export interface ObjectivesImport {
  categories: ObjectiveCategory[];
}

/** Nombres de sobres leídos de la tabla de traducciones de la web app (id → nombre). */
export interface PacksMessage {
  source: "fcsl-packs";
  names: Record<string, string>;
}

export interface PageMessage {
  source: "fcsl";
  url: string;
  body: unknown;
}

export interface Config {
  apiUrl: string;
  token: string;
  rawMode: boolean;
  /** Al iniciar sesión, leer club y Almacén SBC sin navegar (como EasySBC). */
  autoImport: boolean;
}

export interface StatusMessage {
  source: "fcsl-status";
  kind: "auto-import";
  at: string;
  ok: boolean;
  clubPages: number;
  storage: boolean;
  error?: string;
  /** Ids de todo el club, solo si se leyó completo (retrievedAll). */
  clubItemIds?: number[];
}

export interface Stats {
  lastSentAt: string | null;
  lastError: string | null;
  lastAutoImport: string | null;
  errors: number;
  totalItems: number;
  totalObservations: number;
  totalRaw: number;
}

export const DEFAULT_CONFIG: Config = { apiUrl: "http://localhost:8787", token: "", rawMode: false, autoImport: true };
export const EMPTY_STATS: Stats = {
  lastSentAt: null,
  lastError: null,
  lastAutoImport: null,
  errors: 0,
  totalItems: 0,
  totalObservations: 0,
  totalRaw: 0,
};
