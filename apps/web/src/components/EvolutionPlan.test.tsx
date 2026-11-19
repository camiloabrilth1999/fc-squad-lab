import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EvolutionPlan from "./EvolutionPlan";

const URL_ = "http://localhost:8787";

const assignment = (id: number, evo: string, card: string, before: number, after: number) => ({
  evolution: { id, name: evo, category: "Evoluciones" },
  card: { item_id: id, name: card, rating: 70, positions: ["CAM", "CM"] },
  meta_before: before,
  meta_after: after,
  meta_gain: Math.round((after - before) * 10) / 10,
});
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("EvolutionPlan", () => {
  it("lista la asignación con el meta antes y después y la mejora total", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json({
          assignments: [
            assignment(1, "Bajo los focos", "Iron Gomis", 68.6, 78.1),
            assignment(2, "Volante a la derecha", "Féli Delacauw", 67.5, 78.9),
          ],
          total_gain: 20.9,
          evolutions_considered: 9,
        }),
      ),
    );
    render(<EvolutionPlan apiUrl={URL_} />);
    expect(await screen.findByText("Bajo los focos")).toBeInTheDocument();
    expect(screen.getByText(/Iron Gomis/)).toBeInTheDocument();
    expect(screen.getByText(/68\.6 → 78\.1/)).toBeInTheDocument();
    expect(screen.getByText("+20.9")).toBeInTheDocument();
    expect(screen.getByText("(2 de 9 evoluciones)")).toBeInTheDocument();
  });

  it("recalcula con el meta final mínimo elegido", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json({ assignments: [], total_gain: 0, evolutions_considered: 9 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<EvolutionPlan apiUrl={URL_} />);
    await screen.findByText(/Ninguna evolución mejora una carta tuya/);
    expect(new URL(fetchMock.mock.calls[0][0]).searchParams.get("min_after")).toBe("70");

    fireEvent.change(screen.getByLabelText("Meta final mínimo"), { target: { value: "80" } });
    fireEvent.click(screen.getByRole("button", { name: "Calcular" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("min_after")).toBe("80"),
    );
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<EvolutionPlan apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo calcular el plan.")).toBeInTheDocument();
  });
});
