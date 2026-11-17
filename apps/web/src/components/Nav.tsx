import Link from "next/link";

export const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/mi-club", label: "Mi club" },
  { href: "/sbc", label: "SBC" },
  { href: "/plantillas", label: "Plantillas" },
  { href: "/evoluciones", label: "Evoluciones" },
  { href: "/objetivos", label: "Objetivos" },
];

export default function Nav() {
  return (
    <nav className="flex items-center gap-6 border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
      <Link href="/" className="font-semibold">
        FC Squad Lab
      </Link>
      <ul className="flex gap-4 text-sm">
        {NAV_ITEMS.map(({ href, label }) => (
          <li key={href}>
            <Link href={href} className="hover:underline">
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
