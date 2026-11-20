import SbcBrowser from "@/components/SbcBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">SBC</h1>
      <p className="mt-1 text-muted">
        Resuelve cualquier reto con las cartas de tu club, al menor coste. Sin créditos ni
        suscripción.
      </p>
      <SbcBrowser apiUrl={API_URL} />
    </main>
  );
}
