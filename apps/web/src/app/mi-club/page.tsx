import ClubTable from "@/components/ClubTable";
import DataStatus from "@/components/DataStatus";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-6 px-6 py-10">
      <h1 className="text-2xl font-semibold">Mi club</h1>
      <DataStatus apiUrl={API_URL} />
      <ClubTable apiUrl={API_URL} />
    </main>
  );
}
