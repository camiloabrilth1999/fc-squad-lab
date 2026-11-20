import PlayersBrowser from "@/components/PlayersBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Jugadores</h1>
      <p className="mt-1 text-muted">
        Todas las cartas con su meta rating, tier y precio. Filtra y ordena sin créditos ni
        suscripción.
      </p>
      <PlayersBrowser apiUrl={API_URL} />
    </main>
  );
}
