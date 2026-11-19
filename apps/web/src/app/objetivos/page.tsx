import ObjectivesBrowser from "@/components/ObjectivesBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Objetivos</h1>
      <p className="mt-1 text-muted">
        Tus objetivos de EA con su progreso y recompensas. Se importan solos al abrir FC Hub →
        Objetivos en la web app con la extensión activa.
      </p>
      <ObjectivesBrowser apiUrl={API_URL} />
    </main>
  );
}
