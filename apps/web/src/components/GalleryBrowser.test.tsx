import { fireEvent, render, screen } from "@testing-library/react";
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

const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function mockApi() {
  const fn = vi.fn(async (url: string) => (String(url).includes("/solve") ? json(solution) : json({ items: sets })));
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
    expect(screen.getByText("coleccionada")).toBeInTheDocument();
    expect(screen.getByText(/puntos estimados/)).toBeInTheDocument();
    const solveUrl = new URL(String(fn.mock.calls.at(-1)![0]));
    expect(solveUrl.pathname).toBe("/gallery/1/solve");
    expect(solveUrl.searchParams.get("grade")).toBe("A");
    expect(solveUrl.searchParams.get("complete")).toBe("true");
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("red")));
    render(<GalleryBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar la Galería.")).toBeInTheDocument();
  });
});
