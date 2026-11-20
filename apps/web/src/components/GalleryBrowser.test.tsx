import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GalleryBrowser from "./GalleryBrowser";

const URL_ = "http://localhost:8787";

const grades = [
  { name: "D", threshold: 10, tokens: 0 },
  { name: "C", threshold: 500, tokens: 0 },
  { name: "B", threshold: 800, tokens: 5 },
  { name: "A", threshold: 1200, tokens: 8 },
  { name: "S", threshold: 1700, tokens: 15 },
];
const sets = [
  { id: 1, name: "Lecce", group: "serie-a", group_name: "Serie A", required: 15, tokens: 28, grades, collected: 2, points: 900, grade: "B" },
  { id: 2, name: "Monaco", group: "ligue-1", group_name: "Ligue 1", required: 15, tokens: 38, grades, collected: 0, points: 0, grade: null },
];
const solution = {
  set_id: 1,
  name: "Lecce",
  grade: "A",
  threshold: 1200,
  required: 15,
  status: "optimal",
  points: 1360,
  cost: 10300,
  tax: 515,
  coins_needed: 1100,
  buys: 14,
  estimated: true,
  cards: [
    { resource_id: 1, name: "Falcone", rating: 84, positions: ["GK"], image_path: null, points: 830, exact: true, price: 1100, collected: false },
    { resource_id: 2, name: "Propio", rating: 70, positions: ["CM"], image_path: null, points: 35, exact: false, price: null, collected: true },
  ],
};

const planBody = {
  status: "optimal",
  tokens: 752,
  tax: 24011,
  cost: 480250,
  transfers: 510,
  coins_needed: 25750,
  sets: 1,
  max_tokens: 2554,
  saved_tax: 1273,
  items: [
    { set_id: 1, name: "Lecce", image_path: null, from_grade: "B", grade: "S", tokens: 28, points: 1800, cost: 5000, tax: 250, buys: 14, coins_needed: 900 },
  ],
};

const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function mockApi() {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- el 2.º parámetro fija el tipo de las llamadas
  const fn = vi.fn(async (url: string, _init?: RequestInit) => {
    const u = String(url);
    if (u.includes("/gallery/plan")) return json(planBody);
    if (u.includes("/gallery/collected")) return json({ updated: 1 });
    if (u.includes("/cards")) return json({ cards: solution.cards, shown: 2 });
    return u.includes("/solve") ? json(solution) : json({ items: sets });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("GalleryBrowser", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lista los sets con su progreso y filtra por búsqueda y grupo", async () => {
    mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    expect(await screen.findByText("Lecce")).toBeInTheDocument();
    expect(screen.getByText("2/15")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar set"), { target: { value: "mon" } });
    expect(screen.queryByText("Lecce")).not.toBeInTheDocument();
    expect(screen.getByText("Monaco")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar set"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Serie A" }));
    expect(screen.queryByText("Monaco")).not.toBeInTheDocument();
  });

  it("resuelve un grado y muestra coste, impuestos y cartas", async () => {
    const fn = mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: /Lecce/ }));
    // por defecto sugiere el siguiente grado al alcanzado (B → A)
    fireEvent.click(screen.getByRole("button", { name: /Resolver grado A/ }));
    expect(await screen.findByText("Solución óptima")).toBeInTheDocument();
    expect(screen.getByText("10.300")).toBeInTheDocument();
    expect(screen.getByText("515")).toBeInTheDocument();
    expect(screen.getByText("Falcone")).toBeInTheDocument();
    expect(screen.getByText("coleccionada ✓")).toBeInTheDocument();
    expect(screen.getByText(/puntos estimados/)).toBeInTheDocument();
    const solveUrl = new URL(String(fn.mock.calls.at(-1)![0]));
    expect(solveUrl.pathname).toBe("/gallery/1/solve");
    expect(solveUrl.searchParams.get("grade")).toBe("A");
    expect(solveUrl.searchParams.get("complete")).toBe("true");
  });

  it("calcula el plan de fichas con los límites y abre un set del plan", async () => {
    const fn = mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    await screen.findByText("Lecce");
    fireEvent.click(screen.getByRole("button", { name: "Plan de fichas" }));
    fireEvent.change(screen.getByLabelText("Objetivo de fichas"), { target: { value: "751" } });
    fireEvent.change(screen.getByLabelText("Saldo de monedas"), { target: { value: "30000" } });
    fireEvent.click(screen.getByRole("button", { name: "Calcular plan" }));
    expect(await screen.findByText("24.011")).toBeInTheDocument(); // impuestos del plan
    expect(screen.getByText("510")).toBeInTheDocument();
    expect(screen.getByText("1.273")).toBeInTheDocument(); // ahorro por cartas compartidas
    const planUrl = new URL(String(fn.mock.calls.find(([u]) => String(u).includes("/gallery/plan"))![0]));
    expect(planUrl.searchParams.get("target_tokens")).toBe("751");
    expect(planUrl.searchParams.get("max_coins")).toBe("30000");
    expect(planUrl.searchParams.has("max_tax")).toBe(false);
    // abrir el set del plan resuelve su grado
    fireEvent.click(screen.getByRole("button", { name: /Lecce/ }));
    expect(await screen.findByText("Solución óptima")).toBeInTheDocument();
    expect(String(fn.mock.calls.at(-1)![0])).toContain("grade=S");
  });

  it("marca una carta a mano y refresca el progreso", async () => {
    const fn = mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: /Lecce/ }));
    fireEvent.click(screen.getByRole("button", { name: /Resolver grado A/ }));
    await screen.findByText("Solución óptima");
    fireEvent.click(screen.getByRole("button", { name: "Marcar como coleccionada a Falcone" }));
    await waitFor(() => {
      const post = fn.mock.calls.find(([u]) => String(u).includes("/gallery/collected"));
      expect(post).toBeTruthy();
      expect(JSON.parse((post![1] as RequestInit).body as string)).toEqual({ resource_ids: [1], collected: true });
    });
    // tras marcar se vuelve a pedir el progreso y la solución
    await waitFor(() => expect(fn.mock.calls.filter(([u]) => String(u).includes("/solve")).length).toBe(2));
    // una coleccionada se desmarca con otro clic
    fireEvent.click(screen.getByRole("button", { name: "Desmarcar a Propio" }));
    await waitFor(() => {
      const posts = fn.mock.calls.filter(([u]) => String(u).includes("/gallery/collected"));
      expect(JSON.parse((posts.at(-1)![1] as RequestInit).body as string)).toEqual({ resource_ids: [2], collected: false });
    });
  });

  it("marca todas las compradas de la solución de una vez", async () => {
    const fn = mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: /Lecce/ }));
    fireEvent.click(screen.getByRole("button", { name: /Resolver grado A/ }));
    fireEvent.click(await screen.findByRole("button", { name: /marcar las 14 como coleccionadas/ }));
    await waitFor(() => {
      const post = fn.mock.calls.find(([u]) => String(u).includes("/gallery/collected"));
      expect(JSON.parse((post![1] as RequestInit).body as string)).toEqual({ resource_ids: [1], collected: true });
    });
  });

  it("lista las cartas del set con búsqueda para marcarlas", async () => {
    const fn = mockApi();
    render(<GalleryBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: /Lecce/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ver y marcar las cartas del set" }));
    expect(await screen.findByText("Falcone")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar carta del set"), { target: { value: "falc" } });
    await waitFor(() => expect(String(fn.mock.calls.at(-1)![0])).toContain("/gallery/1/cards?q=falc"));
  });

  it("explica un objetivo inalcanzable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        String(url).includes("/gallery/plan")
          ? json({ ...planBody, status: "infeasible", items: [], max_tokens: 300 })
          : json({ items: sets }),
      ),
    );
    render(<GalleryBrowser apiUrl={URL_} />);
    await screen.findByText("Lecce");
    fireEvent.click(screen.getByRole("button", { name: "Plan de fichas" }));
    fireEvent.click(screen.getByRole("button", { name: "Calcular plan" }));
    expect(await screen.findByText(/Ese objetivo no es alcanzable/)).toBeInTheDocument();
    expect(screen.getByText(/300 fichas/)).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("red")));
    render(<GalleryBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar la Galería.")).toBeInTheDocument();
  });
});
