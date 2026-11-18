import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PlayerCard from "./PlayerCard";

describe("PlayerCard", () => {
  it("muestra nombre, media, posiciones y precio", () => {
    render(
      <PlayerCard
        player={{ name: "Jugador X", rating: 88, positions: ["ST", "CF"], price: 12000 }}
      />,
    );
    expect(screen.getByText("Jugador X")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("ST")).toBeInTheDocument();
    expect(screen.getByLabelText("precio")).toHaveTextContent("12.000");
  });

  it("intransferible en vez de precio", () => {
    render(
      <PlayerCard player={{ name: "Y", rating: 80, positions: ["CB"], price: 500, untradeable: true }} />,
    );
    expect(screen.getByText("Intransferible")).toBeInTheDocument();
    expect(screen.queryByLabelText("precio")).not.toBeInTheDocument();
  });

  it("carta desconocida sin media", () => {
    render(<PlayerCard player={{ name: null, rating: null, positions: [] }} />);
    expect(screen.getByText("Carta desconocida")).toBeInTheDocument();
    expect(screen.getByText("–")).toBeInTheDocument();
  });
});
