import EvolutionsBrowser from "@/components/EvolutionsBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Evoluciones</h1>
      <p className="mt-1 text-muted">
        Las evoluciones de la Academia de EA con sus mejoras, costes, caducidad y objetivos. Se
        importan solas al abrir Evoluciones en la web app con la extensión activa.
      </p>
      <EvolutionsBrowser apiUrl={API_URL} />
    </main>
  );
}
