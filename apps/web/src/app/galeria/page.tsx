import GalleryBrowser from "@/components/GalleryBrowser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Galería</h1>
      <p className="mt-1 text-muted">
        Qué cartas coleccionar en cada set de la Galería para llegar a un grado al menor coste
        (compra y venta inmediata, con el 5 % de impuestos).
      </p>
      <GalleryBrowser apiUrl={API_URL} />
    </main>
  );
}
