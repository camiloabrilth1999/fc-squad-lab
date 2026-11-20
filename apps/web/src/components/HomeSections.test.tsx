import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import HomeSections from "./HomeSections";

const club = {
  items: [
    { item_id: 1, name: "Bajo", positions: ["CM"], price: 100, meta: 70, tier: "B", loan: false },
    { item_id: 2, name: "Alto", positions: ["ST"], price: 5000, meta: 90, tier: "S", loan: false },
    { item_id: 3, name: "Cedido", positions: ["LW"], price: null, meta: 95, tier: "S", loan: true },
  ],
};

function mockApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => {
      const path = new URL(url).pathname;
      const body =
        path === "/club"
          ? club
          : path === "/value/bargains"
            ? { items: [{ resource_id: 9, name: "Chollo", positions: ["CB"], price: 650, meta: 82, tier: "A+", meta_source: "stats" }] }
            : path === "/evolutions/plan"
              ? { assignments: [{}, {}], total_gain: 12.5 }
              : { items: [{ id: 1, type: 1, title: "Reto", status: "in_progress", ends_at: new Date(Date.now() + 3_600_000 * 5).toISOString() }] };
      return { ok: true, json: async () => body };
    }),
  );
}

describe("HomeSections", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the best club cards by meta without loans, bargains, plan and objectives", async () => {
    mockApi();
    render(<HomeSections apiUrl="http://localhost:8787" />);
    expect(await screen.findByText("Lo mejor de tu club")).toBeInTheDocument();
    const names = screen.getAllByTitle(/^(Alto|Bajo|Cedido)$/).map((e) => e.textContent);
    expect(names).toEqual(["Alto", "Bajo"]);
    expect(await screen.findByText("Chollo")).toBeInTheDocument();
    expect(await screen.findByText(/\+12\.5/)).toBeInTheDocument();
    expect(await screen.findByText("Reto")).toBeInTheDocument();
  });

  it("renders nothing when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    const { container } = render(<HomeSections apiUrl="http://localhost:8787" />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container.textContent).toBe("");
  });
});
