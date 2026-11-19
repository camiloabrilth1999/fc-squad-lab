import SquadBuilder from "@/components/SquadBuilder";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Plantillas</h1>
      <p className="mt-1 text-muted">Tu mejor once por formación y química, con tus cartas.</p>
      <SquadBuilder apiUrl={API_URL} />
    </main>
  );
}
