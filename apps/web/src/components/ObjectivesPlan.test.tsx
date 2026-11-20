import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ObjectivesPlan from "./ObjectivesPlan";

const URL_ = "http://localhost:8787";

const task = (id: number, text: string, extra: Record<string, unknown> = {}) => ({
  objective_id: id,
  group: "Maestría en Rivals",
  text,
  kind: "win",
  scope_label: "Rivals",
  progress: 0,
  target: 10,
  remaining: 10,
  matches: 17,
  constraints: [],
  notes: [],
  unresolved: [],
  ...extra,
});

const candidates = {
  plannable: [task(1, "Gana 10 partidos de Rivals."), task(2, "Juega 5 partidos de Rivals.", { matches: 5 })],
  skipped: [{ objective_id: 9, group: "Mercado", text: "Pon a 500 futbolistas en el Mercado.", reason: "se hace en el Mercado de transferibles" }],
};

const planBody = {
  sessions: [
    {
      scope: "rivals",
      label: "Rivals",
      matches: 17,
      constraints: [{ kind: "league", id: 13, name: "Premier League", k: 3 }],
      tasks: [task(1, "Gana 10 partidos de Rivals."), task(2, "Juega 5 partidos de Rivals.", { matches: 5 })],
    },
  ],
  dropped: [],
  skipped: [],
  totals: { objectives: 2, matches: 17, matches_separate: 22, saved: 5 },
  assumptions: { win_rate: 0.6, goals_per_match: 2, assists_per_match: 1.2 },
};

const squad = {
  status: "optimal",
  formation: "442",
  team_rating: 84,
  team_chemistry: 30,
  slots: [{ slot_index: 0, position: "ST", name: "Delantero Uno", rating: 85, image_path: null }],
};

const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function mockApi() {
  const fn = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes("/objectives/plan/candidates")) return json(candidates);
    if (u.includes("/objectives/plan/squad")) return json(squad);
    return json(planBody);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("ObjectivesPlan", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lista los objetivos planificables y explica los que no", async () => {
    mockApi();
    render(<ObjectivesPlan apiUrl={URL_} />);
    expect(await screen.findByRole("button", { name: "Planificar 2 objetivos" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Ver los 1 que no se pueden planificar/ }));
    expect(screen.getByText(/Mercado de transferibles/)).toBeInTheDocument();
  });

  it("planifica solo lo marcado y muestra sesiones, mínimos y ahorro", async () => {
    const fn = mockApi();
    render(<ObjectivesPlan apiUrl={URL_} />);
    await screen.findByRole("button", { name: "Planificar 2 objetivos" });
    fireEvent.click(screen.getByLabelText("Juega 5 partidos de Rivals.")); // desmarca uno
    fireEvent.change(screen.getByLabelText("Partidos que ganas (%)"), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Planificar 1 objetivos" }));
    expect(await screen.findByText("~17 partidos")).toBeInTheDocument();
    expect(screen.getByText("mín. 3 de la liga Premier League")).toBeInTheDocument();
    expect(screen.getByText("22")).toBeInTheDocument(); // por separado
    expect(screen.getByText("5")).toBeInTheDocument(); // ahorro
    const url = new URL(String(fn.mock.calls.find(([u]) => String(u).includes("/objectives/plan?"))![0]));
    expect(url.searchParams.get("ids")).toBe("1");
    expect(url.searchParams.get("win_rate")).toBe("0.5");
  });

  it("carga la plantilla de una sesión con sus mínimos", async () => {
    const fn = mockApi();
    render(<ObjectivesPlan apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Planificar 2 objetivos" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ver plantilla" }));
    expect(await screen.findByText("Delantero Uno")).toBeInTheDocument();
    expect(screen.getByText(/442 · media 84 · química 30/)).toBeInTheDocument();
    await waitFor(() => {
      const u = String(fn.mock.calls.find(([x]) => String(x).includes("/plan/squad"))![0]);
      expect(decodeURIComponent(u)).toContain("mins=league:13:3");
    });
  });

  it("muestra un mensaje si no hay nada que planificar", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ plannable: [], skipped: [] })));
    render(<ObjectivesPlan apiUrl={URL_} />);
    expect(await screen.findByText(/No hay objetivos de partidos pendientes/)).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("red")));
    render(<ObjectivesPlan apiUrl={URL_} />);
    expect(await screen.findByText(/No se pudieron cargar los objetivos planificables/)).toBeInTheDocument();
  });
});
