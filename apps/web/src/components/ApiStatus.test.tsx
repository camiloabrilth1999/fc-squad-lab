import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ApiStatus from "./ApiStatus";

const URL_ = "http://localhost:8787";

function mockFetchJson(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => body }));
}

describe("ApiStatus", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows connected", async () => {
    mockFetchJson({ status: "ok", db: "ok" });
    render(<ApiStatus apiUrl={URL_} />);
    expect(await screen.findByText("API conectada")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(`${URL_}/health`, expect.anything());
  });

  it("shows connected when db is unchecked", async () => {
    mockFetchJson({ status: "ok", db: "unchecked" });
    render(<ApiStatus apiUrl={URL_} />);
    expect(await screen.findByText("API conectada")).toBeInTheDocument();
  });

  it("shows db down", async () => {
    mockFetchJson({ status: "ok", db: "down" });
    render(<ApiStatus apiUrl={URL_} />);
    expect(await screen.findByText("Base de datos caída")).toBeInTheDocument();
  });

  it("shows offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    render(<ApiStatus apiUrl={URL_} />);
    expect(await screen.findByText("API sin conexión")).toBeInTheDocument();
  });
});
