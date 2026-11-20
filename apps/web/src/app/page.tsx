import Link from "next/link";
import ApiStatus from "@/components/ApiStatus";
import HomeSections from "@/components/HomeSections";
import HomeStats from "@/components/HomeStats";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

const TOOLS: { href: string; title: string; desc: string; icon: string }[] = [
  { href: "/mi-club", title: "Mi club", desc: "Tu plantilla importada con precios y valor.", icon: "⚽" },
  { href: "/sbc", title: "SBC", desc: "Resuelve retos con las cartas de tu club, al menor coste.", icon: "🧩" },
  { href: "/plantillas", title: "Plantillas", desc: "Tu mejor once por formación y química.", icon: "📋" },
  { href: "/evoluciones", title: "Evoluciones", desc: "Qué jugadores evolucionar y las mejores rutas.", icon: "📈" },
  { href: "/objetivos", title: "Objetivos", desc: "Sigue y planifica tus objetivos.", icon: "🎯" },
];

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <section className="rounded-card border border-line bg-gradient-to-br from-surface to-surface-2 p-6 sm:p-8">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
          <span className="text-xs font-medium uppercase tracking-wider text-muted">
            Tu laboratorio de Ultimate Team
          </span>
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">FC Squad Lab</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Importa tu club automáticamente y resuelve SBC, arma plantillas y planifica evoluciones
          con tus propias cartas y precios en tiempo real. Sin suscripción.
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            href="/sbc"
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong"
          >
            Resolver un SBC
          </Link>
          <Link
            href="/mi-club"
            className="rounded-lg border border-line px-4 py-2 text-sm font-medium transition-colors hover:bg-surface-2"
          >
            Ver mi club
          </Link>
          <span className="ml-auto">
            <ApiStatus apiUrl={API_URL} />
          </span>
        </div>
      </section>

      <HomeStats apiUrl={API_URL} />
      <HomeSections apiUrl={API_URL} />

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="group rounded-card border border-line bg-surface p-5 transition-colors hover:border-accent/50 hover:bg-surface-2"
          >
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-surface-2 text-lg" aria-hidden>
                {t.icon}
              </span>
              <h2 className="font-medium">{t.title}</h2>
              <span className="ml-auto text-muted transition-transform group-hover:translate-x-0.5" aria-hidden>
                →
              </span>
            </div>
            <p className="mt-3 text-sm text-muted">{t.desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
