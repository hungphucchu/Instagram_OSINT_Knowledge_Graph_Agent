"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/chat", label: "Knowledge Chat" },
  { href: "/agents", label: "Pipeline Console" },
  { href: "/graph", label: "Graph Explorer" }
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="brand-header" style={{ marginBottom: '2.5rem', padding: '0 0.5rem' }}>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.15em', color: '#64748b', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
          Instagram OSINT
        </div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, lineHeight: 1.2, color: '#f8fafc' }}>
          KG <span style={{ color: '#3b82f6' }}>Agent</span>
        </h1>
      </div>
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
