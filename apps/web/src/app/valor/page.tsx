import ValueViews from "@/components/ValueViews";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Valor</h1>
      <p className="mt-1 text-muted">
        Dónde está el dinero bien gastado: chollos por meta rating y fodder barato para SBC.
      </p>
      <ValueViews apiUrl={API_URL} />
    </main>
  );
}
