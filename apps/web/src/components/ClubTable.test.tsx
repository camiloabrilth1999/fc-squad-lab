import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ClubTable from "./ClubTable";

const URL_ = "http://localhost:8787";

const row = (over: Record<string, unknown> = {}) => ({
  item_id: 1,
  resource_id: 100,
  name: "Vinícius Jr",
  rating: 91,
  positions: ["LW", "ST"],
  league_id: 53,
  nation_id: 54,
  club_id: 243,
  rarity_name: "Rare",
  untradeable: false,
  location: "club",
  duplicate: false,
  loan: false,
  price: 40250,
  price_source: "ea-session",
  value: 40250,
  seen_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
  ...over,
});

function mockClub(items: unknown[], total = items.length, summary?: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      items,
      total,
      summary: summary ?? { count: total, value: 1234567, untradeable: 0, unknown_cards: 0 },
    }),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const lastUrl = (fn: ReturnType<typeof vi.fn>) => new URL(fn.mock.calls.at(-1)![0] as string);

const clubBody = (items: unknown[]) => ({
  items,
  total: items.length,
  summary: { count: items.length, value: 0, untradeable: 0, unknown_cards: 0 },
});

/** fetch que responde /club con `items` y /club/forget con `forget` (status, cuerpo). */
function mockApi(items: unknown[], forget: { status: number; body: unknown } = { status: 200, body: { deleted: 2 } }) {
  const fn = vi.fn().mockImplementation(async (url: string) => {
    if (new URL(url).pathname === "/club/forget") {
      return { ok: forget.status < 300, status: forget.status, json: async () => forget.body };
    }
    return { ok: true, status: 200, json: async () => clubBody(items) };
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const forgetCalls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.filter(([url]) => new URL(url as string).pathname === "/club/forget");

describe("ClubTable", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders rows, unknown cards, formatted coins, source and summary", async () => {
    mockClub([row(), row({ item_id: 2, resource_id: 123, name: null, price: null, price_source: null, value: 0 })]);
    render(<ClubTable apiUrl={URL_} />);
    expect(await screen.findByText("Vinícius Jr")).toBeInTheDocument();
    expect(screen.getByText("Carta desconocida #123")).toBeInTheDocument();
    expect(screen.getAllByText("40.250").length).toBeGreaterThan(0);
    expect(screen.getByText("Mercado (tu sesión)")).toBeInTheDocument();
    expect(screen.getByText("1.234.567")).toBeInTheDocument();
  });

  it("requests page 1 with page_size 50 and sends filters in the URL", async () => {
    const fn = mockClub([row()]);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    const first = lastUrl(fn);
    expect(first.pathname).toBe("/club");
    expect(first.searchParams.get("page")).toBe("1");
    expect(first.searchParams.get("page_size")).toBe("50");
    expect(first.searchParams.has("location")).toBe(false);

    fireEvent.change(screen.getByLabelText("Media mín"), { target: { value: "85" } });
    await waitFor(() => expect(lastUrl(fn).searchParams.get("min_rating")).toBe("85"));
    fireEvent.change(screen.getByLabelText("Ubicación"), { target: { value: "storage" } });
    await waitFor(() => expect(lastUrl(fn).searchParams.get("location")).toBe("storage"));
    fireEvent.click(screen.getByLabelText("Solo intransferibles"));
    await waitFor(() => expect(lastUrl(fn).searchParams.get("untradeable")).toBe("true"));
  });

  it("paginates", async () => {
    const fn = mockClub([row()], 120);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(lastUrl(fn).searchParams.get("page")).toBe("2"));
    expect(screen.getByRole("button", { name: "Anterior" })).toBeEnabled();
  });

  it("shows the empty state with a hint", async () => {
    mockClub([], 0, { count: 0, value: 0, untradeable: 0, unknown_cards: 0 });
    render(<ClubTable apiUrl={URL_} />);
    expect(await screen.findByText(/Abre la web app de EA con la extensión activa/)).toBeInTheDocument();
  });

  it("labels the default location as excluding the watchlist", async () => {
    mockClub([row()]);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    expect(screen.getByRole("option", { name: "Todas (sin lista de seguimiento)" })).toBeInTheDocument();
  });

  it("shows when each card was last seen", async () => {
    mockClub([row(), row({ item_id: 2, name: "Otro", seen_at: null })]);
    render(<ClubTable apiUrl={URL_} />);
    expect(await screen.findByText("Visto hace 3 días")).toBeInTheDocument();
    expect(screen.getByText("Nunca visto")).toBeInTheDocument();
  });

  it("toggles cards not seen in 30 days with max_age_days=0", async () => {
    const fn = mockClub([row()]);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    expect(lastUrl(fn).searchParams.has("max_age_days")).toBe(false);
    fireEvent.click(screen.getByLabelText("Mostrar cartas no vistas en 30 días"));
    await waitFor(() => expect(lastUrl(fn).searchParams.get("max_age_days")).toBe("0"));
    expect(lastUrl(fn).searchParams.get("page")).toBe("1");
  });

  it("remembers the import token in localStorage", async () => {
    localStorage.setItem("fcsl.importToken", "guardado");
    mockApi([row()]);
    render(<ClubTable apiUrl={URL_} />);
    const tokenInput = screen.getByLabelText("Token de importación");
    await waitFor(() => expect(tokenInput).toHaveValue("guardado"));
    fireEvent.change(tokenInput, { target: { value: "nuevo" } });
    expect(localStorage.getItem("fcsl.importToken")).toBe("nuevo");
  });

  it("works when localStorage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    mockApi([row()]);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    fireEvent.change(screen.getByLabelText("Token de importación"), { target: { value: "t" } });
    expect(screen.getByLabelText("Token de importación")).toHaveValue("t");
  });

  it("forgets stale cards after confirming, with the token, and reloads", async () => {
    const fn = mockApi([row()]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    const loads = fn.mock.calls.length;
    fireEvent.change(screen.getByLabelText("Token de importación"), { target: { value: "secreto" } });
    fireEvent.click(screen.getByRole("button", { name: "Olvidar cartas no vistas en 30 días" }));
    expect(await screen.findByText("Olvidadas 2 cartas")).toBeInTheDocument();
    expect(confirm).toHaveBeenCalledTimes(1);
    const [[url, init]] = forgetCalls(fn);
    expect(url).toBe(`${URL_}/club/forget`);
    expect(init.method).toBe("POST");
    expect(init.headers["X-FCSL-Token"]).toBe("secreto");
    expect(JSON.parse(init.body)).toEqual({ older_than_days: 30 });
    await waitFor(() => expect(fn.mock.calls.length).toBeGreaterThan(loads + 1));
  });

  it("does nothing when the confirm dialog is cancelled", async () => {
    const fn = mockApi([row()]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    fireEvent.change(screen.getByLabelText("Token de importación"), { target: { value: "secreto" } });
    fireEvent.click(screen.getByRole("button", { name: "Olvidar cartas no vistas en 30 días" }));
    expect(forgetCalls(fn)).toHaveLength(0);
  });

  it("asks for the token before forgetting", async () => {
    const fn = mockApi([row()]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    fireEvent.click(screen.getByRole("button", { name: "Olvidar cartas no vistas en 30 días" }));
    expect(await screen.findByText("Falta el token de importación")).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    expect(forgetCalls(fn)).toHaveLength(0);
  });

  it("reports an invalid token", async () => {
    mockApi([row()], { status: 401, body: { detail: "Token de importación inválido" } });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ClubTable apiUrl={URL_} />);
    await screen.findByText("Vinícius Jr");
    fireEvent.change(screen.getByLabelText("Token de importación"), { target: { value: "mal" } });
    fireEvent.click(screen.getByRole("button", { name: "Olvidar cartas no vistas en 30 días" }));
    expect(await screen.findByText("No se pudo olvidar: token de importación inválido")).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    render(<ClubTable apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar el club")).toBeInTheDocument();
  });
});
