"use client";

import { useEffect, useState } from "react";

type State = "loading" | "connected" | "db-down" | "offline";

const LABELS: Record<State, string> = {
  loading: "Comprobando API…",
  connected: "API conectada",
  "db-down": "Base de datos caída",
  offline: "API sin conexión",
};

export default function ApiStatus({ apiUrl }: { apiUrl: string }) {
  const [state, setState] = useState<State>("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiUrl}/health`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { db?: string }) => {
        // "unchecked" = la API aún no comprueba la base de datos; cuenta como conectada.
        setState(data.db === "down" ? "db-down" : "connected");
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setState("offline");
      });
    return () => controller.abort();
  }, [apiUrl]);

  const color =
    state === "connected"
      ? "bg-green-500"
      : state === "loading"
        ? "bg-zinc-400"
        : "bg-red-500";

  return (
    <p className="flex items-center gap-2 text-sm" role="status">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      <span>{LABELS[state]}</span>
    </p>
  );
}
