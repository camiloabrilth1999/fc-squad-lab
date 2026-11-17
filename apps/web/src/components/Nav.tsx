"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_ITEMS: { href: string; label: string; icon: string }[] = [
  { href: "/mi-club", label: "Mi club", icon: "⚽" },
  { href: "/sbc", label: "SBC", icon: "🧩" },
  { href: "/plantillas", label: "Plantillas", icon: "📋" },
  { href: "/evoluciones", label: "Evoluciones", icon: "📈" },
  { href: "/objetivos", label: "Objetivos", icon: "🎯" },
];

function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-20 border-b border-line bg-bg/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-2 px-4 py-2.5 sm:gap-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 pr-2 font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-sm text-accent-fg">
            FC
          </span>
          <span className="hidden sm:inline">Squad Lab</span>
        </Link>
        <ul className="flex flex-1 items-center gap-0.5 overflow-x-auto text-sm sm:gap-1">
          {NAV_ITEMS.map(({ href, label, icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 transition-colors sm:px-3 ${
                    active
                      ? "bg-surface-2 font-medium text-fg"
                      : "text-muted hover:bg-surface-2 hover:text-fg"
                  }`}
                >
                  <span aria-hidden>{icon}</span>
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
