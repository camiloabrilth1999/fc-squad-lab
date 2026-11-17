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

describe("ClubTable", () => {
  afterEach(() => vi.unstubAllGlobals());

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

  it("shows an error state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    render(<ClubTable apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar el club")).toBeInTheDocument();
  });
});
