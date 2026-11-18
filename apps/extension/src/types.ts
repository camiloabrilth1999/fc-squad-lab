export type Location = "club" | "storage" | "tradepile" | "watchlist";
export type Endpoint = Location | "market";

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
