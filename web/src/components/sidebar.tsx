"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/chat", label: "Chat Interface" },
  { href: "/agents", label: "Run Agents" },
  { href: "/graph", label: "Graph Display" }
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <h1>Instagram KG</h1>
      <p className="muted">OSINT Agent Console</p>
      <nav>
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} className={`nav-item ${active ? "active" : ""}`}>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
