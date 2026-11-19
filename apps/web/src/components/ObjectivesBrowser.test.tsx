import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ObjectivesBrowser from "./ObjectivesBrowser";

const URL_ = "http://localhost:8787";

const group = (id: number, title: string, extra: Record<string, unknown> = {}) => ({
  id,
  type: 6,
  title,
  subtitle: `Subtítulo de ${title}`,
  category_id: 0,
  category: "Fundamentos",
  status: "in_progress",
  repeatability: "NON_REPEATABLE",
  times_completed: 0,
  ends_at: null,
  progress: { done: 1, total: 3 },
  awards: [
    { type: "coin", label: "5.000 monedas", count: 1 },
    { type: "pack", label: "Sobre #304", count: 1 },
  ],
  objectives: [
    { id: 1, name: "Juega 3 partidos", description: null, progress: 3, target: 3, state: "REDEEMED", awards: [] },
    {
      id: 2,
      name: "Marca 10 goles",
      description: null,
      progress: 4,
      target: 10,
      state: "IN_PROGRESS",
      awards: [{ type: "xp", label: "+200 XP", count: 1 }],
    },
  ],
  ...extra,
});
const cats = [
  { id: 0, name: "Fundamentos", groups: 4, done: 1 },
  { id: 1, name: "Hitos", groups: 13, done: 0 },
];
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const router = (list: unknown) =>
  vi.fn().mockImplementation(async (url: string) =>
    String(url).includes("/objectives/categories") ? json(cats) : json(list),
  );

afterEach(() => vi.unstubAllGlobals());

describe("ObjectivesBrowser", () => {
  it("lista grupos con estado, progreso y recompensas", async () => {
    vi.stubGlobal("fetch", router({ items: [group(1, "Fútbol total")], total: 1 }));
    render(<ObjectivesBrowser apiUrl={URL_} />);
    expect(await screen.findByText("Fútbol total")).toBeInTheDocument();
    expect(screen.getByText("En curso")).toBeInTheDocument();
    expect(screen.getByText("1/3 objetivos")).toBeInTheDocument();
    expect(screen.getByText(/5\.000 monedas · Sobre #304/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Progreso de Fútbol total" })).toHaveAttribute(
      "aria-valuenow",
      "33",
    );
  });

  it("muestra las categorías con lo completado y filtra al elegir una", async () => {
    const fetchMock = router({ items: [group(1, "A")], total: 1 });
    vi.stubGlobal("fetch", fetchMock);
    render(<ObjectivesBrowser apiUrl={URL_} />);
    const hitos = await screen.findByRole("button", { name: /Hitos/ });
    expect(hitos).toHaveTextContent("0/13");
    fireEvent.click(hitos);
    await waitFor(() => {
      const last = new URL(fetchMock.mock.calls.at(-1)![0]);
      expect(last.pathname).toBe("/objectives");
      expect(last.searchParams.get("category_id")).toBe("1");
    });
  });

  it("filtra por pendientes y completados, y busca por texto", async () => {
    const fetchMock = router({ items: [group(1, "A")], total: 1 });
    vi.stubGlobal("fetch", fetchMock);
    render(<ObjectivesBrowser apiUrl={URL_} />);
    await screen.findByText("A");
    fireEvent.click(screen.getByRole("button", { name: "Pendientes" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("status")).toBe("open"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Completados" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("status")).toBe("done"),
    );
    fireEvent.change(screen.getByLabelText("Buscar objetivo"), { target: { value: "semanal" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("q")).toBe("semanal"),
    );
  });

  it("despliega los objetivos con su progreso", async () => {
    vi.stubGlobal("fetch", router({ items: [group(1, "Fútbol total")], total: 1 }));
    render(<ObjectivesBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver 2 objetivos" }));
    expect(screen.getByText("Marca 10 goles")).toBeInTheDocument();
    expect(screen.getByText("4/10")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument(); // el reclamado
    expect(screen.getByText("+200 XP")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ocultar" }));
    expect(screen.queryByText("Marca 10 goles")).toBeNull();
  });

  it("explica cómo importar cuando no hay nada", async () => {
    vi.stubGlobal("fetch", router({ items: [], total: 0 }));
    render(<ObjectivesBrowser apiUrl={URL_} />);
    expect(await screen.findByText(/Aún no hay objetivos aquí/)).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<ObjectivesBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudieron cargar los objetivos.")).toBeInTheDocument();
  });
});
