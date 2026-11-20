import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SbcBrowser from "./SbcBrowser";

const URL_ = "http://localhost:8787";

const summary = {
  id: "mejora-81",
  set_id: "mejoras",
  set_name: "Mejoras",
  name: "Mejora 81+",
  formation: "442",
  requirements: 1,
  reward: null,
  repeatable: true,
  category: "Mejoras",
  source: "seed",
};
const detail = {
  id: "mejora-81",
  name: "Mejora 81+",
  formation: "442",
  requirements: [{ kind: "TEAM_RATING", op: "min", value: 81 }],
  reward: "Sobre de oro",
};
const solveResult = {
  status: "optimal",
  pool: "club",
  squad: [
    { slot_index: 0, position: "ST", name: "Jugador X", rating: 88, source: "club", untradeable: false, price: null },
  ],
  cost: 0,
  team_rating: 84,
  team_chemistry: 20,
  buys: 0,
  solve_time_s: 0.1,
  message: null,
};

const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function mockApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes("/solve")) return json(solveResult);
      if (u.endsWith("/sbc")) return json([summary]);
      if (u.includes("/sbc/mejora-81")) return json(detail);
      return json({});
    }),
  );
}

describe("SbcBrowser", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lista retos, muestra requisitos y resuelve con el club", async () => {
    mockApi();
    render(<SbcBrowser apiUrl={URL_} />);

    // Lista cargada desde /sbc
    const challenge = await screen.findByRole("button", { name: /Mejora 81\+/ });
    fireEvent.click(challenge);

    // Requisitos desde /sbc/{id}
    expect(await screen.findByText(/Valoración del equipo: mín\. 81/)).toBeInTheDocument();

    // Resolver desde /sbc/{id}/solve
    fireEvent.click(screen.getByRole("button", { name: "Resolver con mi club" }));
    expect(await screen.findByText("Resuelto (óptimo)")).toBeInTheDocument();
    expect(screen.getByText("Jugador X")).toBeInTheDocument();
  });

  it("filtra por búsqueda y por repetibles", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json([
          summary,
          { ...summary, id: "otro", set_id: "otros", set_name: "Otros", name: "Reto único", repeatable: false },
        ]),
      ),
    );
    render(<SbcBrowser apiUrl={URL_} />);
    expect(await screen.findByRole("button", { name: /Reto único/ })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar SBC"), { target: { value: "mejora" } });
    expect(screen.queryByRole("button", { name: /Reto único/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar SBC"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Un solo uso" }));
    expect(screen.queryByRole("button", { name: /Mejora 81\+/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reto único/ })).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("red")));
    render(<SbcBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar los SBC.")).toBeInTheDocument();
  });
});
