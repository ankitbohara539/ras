"use client";

import {
  BellRing,
  Building2,
  CircleUserRound,
  ClipboardList,
  Gauge,
  LogOut,
  Map,
  MapPinned,
  Menu,
  PlusCircle,
  Settings,
  Shield,
  Siren,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Brand } from "@/components/Brand";
import { useAuth } from "@/features/auth/auth-context";
import { primaryRole, rolePath } from "@/lib/auth/roles";
import type { Role } from "@/types";
import { ConnectionIndicator } from "./ConnectionIndicator";
import { NotificationBell } from "./NotificationBell";

const navigation = {
  CITIZEN: [
    ["Overview", "", Gauge],
    ["Report issue", "report", PlusCircle],
    ["My reports", "reports", ClipboardList],
    ["Community map", "map", Map],
    ["Civic services", "services", Building2],
    ["Emergency SOS", "emergency", Siren],
    ["Active alerts", "alerts", BellRing],
  ],
  AUTHORITY: [
    ["Operations", "", Gauge],
    ["Issue queue", "issues", ClipboardList],
    ["Area map", "map", Map],
    ["Publish alerts", "alerts", BellRing],
    ["Civic services", "services", Building2],
  ],
  RESPONDER: [
    ["Response board", "", Gauge],
    ["Active SOS", "emergencies", Siren],
    ["Response map", "map", Map],
  ],
  ADMIN: [
    ["Platform", "", Gauge],
    ["People & roles", "users", Users],
    ["Categories", "categories", ClipboardList],
    ["Areas", "areas", Map],
    ["Services", "services", Building2],
    ["Audit trail", "audit", Shield],
  ],
} satisfies Record<Role, [string, string, typeof Gauge][]>;

export function DashboardShell({
  role,
  children,
}: {
  role: Role;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const home = rolePath(role);
  const activeSection = navigation[role].find(([, route]) => pathname === (route ? home + "/" + route : home));
  useEffect(() => {
    if (!loading && !user) router.replace("/login?next=" + encodeURIComponent(pathname));
    else if (user && !user.roles.includes(role)) router.replace(rolePath(primaryRole(user.roles)));
  }, [loading, pathname, role, router, user]);
  if (loading || !user) return <main className="screen-loader"><span className="spinner" /> Securing your workspace…</main>;
  if (!user.roles.includes(role)) return null;

  const nav = (
    <nav aria-label="Workspace">
      {navigation[role].map(([label, route, Icon]) => {
        const href = route ? home + "/" + route : home;
        return <Link key={label} href={href} className={pathname === href ? "active" : ""} onClick={() => setMobileOpen(false)}><Icon size={19} /><span>{label}</span></Link>;
      })}
    </nav>
  );

  return (
    <div className="dashboard">
      <aside className="command-rail"><Brand /><div className="metro-rail-scope"><MapPinned size={16} /><div><strong>Kathmandu Metro</strong><span>32-ward operations</span></div></div><div className="role-label"><span>{role}</span> workspace</div>{nav}<div className="rail-foot"><ConnectionIndicator /><a href="https://kathmandu.gov.np/en/wards" target="_blank" rel="noreferrer">Official ward directory ↗</a><span>Community command v0.3</span></div></aside>
      {mobileOpen && <div className="mobile-drawer"><button className="drawer-backdrop" onClick={() => setMobileOpen(false)} aria-label="Close navigation" /><aside><div className="drawer-title"><Brand /><button className="icon-button" onClick={() => setMobileOpen(false)}><X /></button></div>{nav}</aside></div>}
      <div className="dashboard-stage">
        <header className="dashboard-header">
          <button className="icon-button menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu /></button>
          <div><span className="header-kicker">Kathmandu civic command</span><strong>{activeSection?.[0] ?? "Overview"}</strong></div>
          <div className="header-actions">
            <ConnectionIndicator />
            <NotificationBell home={home} />
            <div className="account-menu">
              <span className="avatar">{user.full_name.slice(0, 2).toUpperCase()}</span>
              <span className="account-copy"><strong>{user.full_name}</strong><small>{user.email}</small></span>
              <div className="account-actions"><Link href="/settings/profile"><Settings size={17} /> Settings</Link><button onClick={async () => { await logout(); router.replace("/login"); }}><LogOut size={17} /> Sign out</button></div>
            </div>
          </div>
        </header>
        <main className="dashboard-content"><div className="metro-context-bar"><div><MapPinned size={18} /><span><strong>Kathmandu Metropolitan City</strong><small>Ward-level civic operations</small></span></div><span className="scope-pill">32 ward scope</span></div>{children}</main>
        <nav className="mobile-tabs" aria-label="Mobile navigation">
          {navigation[role].slice(0, 4).map(([label, route, Icon]) => { const href = route ? home + "/" + route : home; return <Link key={label} href={href} className={pathname === href ? "active" : ""}><Icon /><span>{label}</span></Link>; })}
          <button onClick={() => setMobileOpen(true)}><CircleUserRound /><span>More</span></button>
        </nav>
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}
