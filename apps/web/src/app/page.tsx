import ApiStatus from "@/components/ApiStatus";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <h1 className="mb-4 text-2xl font-semibold">FC Squad Lab</h1>
      <ApiStatus apiUrl={API_URL} />
    </main>
  );
}
