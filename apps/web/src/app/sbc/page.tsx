const STEPS: { n: number; title: string; desc: string }[] = [
  { n: 1, title: "Importa tu club", desc: "La extensión lee tu club desde la web app de EA. Automático, sin escribir nada." },
  { n: 2, title: "Elige un SBC", desc: "Tus retos activos con sus requisitos, traídos de EA." },
  { n: 3, title: "Resuelve al menor coste", desc: "El solver arma la plantilla más barata con tus cartas y el mercado." },
];

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">SBC</h1>
      <p className="mt-1 text-muted">
        Resuelve cualquier reto con las cartas de tu club, al menor coste. Sin créditos ni
        suscripción.
      </p>

      <ol className="mt-6 grid gap-4 sm:grid-cols-3">
        {STEPS.map((s) => (
          <li key={s.n} className="rounded-card border border-line bg-surface p-5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-semibold text-accent-fg">
              {s.n}
            </span>
            <h2 className="mt-3 font-medium">{s.title}</h2>
            <p className="mt-1 text-sm text-muted">{s.desc}</p>
          </li>
        ))}
      </ol>

      <div className="mt-6 rounded-card border border-dashed border-line bg-surface p-8 text-center">
        <p className="font-medium">Conectando tus retos de EA</p>
        <p className="mx-auto mt-1 max-w-xl text-sm text-muted">
          El motor que resuelve ya está listo. Falta capturar el detalle de requisitos de cada SBC
          desde la web app de EA (vía la extensión) para listarlos y resolverlos aquí.
        </p>
      </div>
    </main>
  );
}
