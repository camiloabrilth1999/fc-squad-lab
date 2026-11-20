import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Nav, { NAV_ITEMS } from "./Nav";

describe("Nav", () => {
  it("renders all sections", () => {
    render(<Nav />);
    const expected = [
      ["Mi club", "/mi-club"],
      ["SBC", "/sbc"],
      ["Plantillas", "/plantillas"],
      ["Jugadores", "/jugadores"],
      ["Valor", "/valor"],
      ["Galería", "/galeria"],
      ["Evoluciones", "/evoluciones"],
      ["Objetivos", "/objetivos"],
    ];
    expect(NAV_ITEMS).toHaveLength(8);
    for (const [label, href] of expected) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", href);
    }
  });
});
