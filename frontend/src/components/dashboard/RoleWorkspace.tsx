"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, Bell, Building2, CheckCircle2, ClipboardList, MapPin, Siren } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import type { Issue, Notification, Page, Role } from "@/types";
import { SOSPanel } from "@/features/emergency/SOSPanel";
import { IssueReportForm } from "@/features/issues/IssueReportForm";
import { MapCard } from "./MapCard";
import { DashboardShell, PageHeader } from "./DashboardShell";

type Alert = { id: string; title: string; message: string; severity: string; created_at: string };
type Service = { id: string; name: string; address: string; phone: string | null; emergency_service: boolean };
type Emergency = { id: string; emergency_type: string; status: string; address_text: string | null; created_at: string; version: number };
type AdminUser = { id: string; full_name: string; email: string; status: string; roles: Role[]; created_at: string };

function StatusBadge({ value }: { value: string }) {
  return <span className={"status-badge status-" + value.toLowerCase()}>{value.replaceAll("_", " ")}</span>;
}

function EmptyState({ title, copy }: { title: string; copy: string }) {
  return <div className="empty-state"><MapPin /><h3>{title}</h3><p>{copy}</p></div>;
}

function IssueList({ mine = false }: { mine?: boolean }) {
  const query = useQuery({ queryKey: ["issues", mine ? "mine" : "all"], queryFn: () => api<Page<Issue>>("/issues?page_size=50" + (mine ? "&mine=true" : "")) });
  if (query.isLoading) return <div className="module-card loading-card">Loading issue records…</div>;
  if (!query.data?.items.length) return <EmptyState title="No issue reports yet" copy="Reports will appear here as soon as they are persisted by the API." />;
  return <div className="record-list">{query.data.items.map((issue) => <article key={issue.id}><div className="record-icon"><ClipboardList /></div><div><h3>{issue.title}</h3><p>{issue.address_text ?? "Location available on map"} · {new Date(issue.created_at).toLocaleDateString()}</p></div><StatusBadge value={issue.status} /></article>)}</div>;
}

function ServiceList() {
  const query = useQuery({ queryKey: ["services"], queryFn: () => api<Page<Service>>("/civic-services?page_size=50") });
  if (!query.data?.items.length) return <EmptyState title="No services published" copy="Verified civic services will appear here; no placeholder listings are generated." />;
  return <div className="card-grid">{query.data.items.map((service) => <article className="directory-card" key={service.id}><Building2 /><div><h3>{service.name}</h3><p>{service.address}</p>{service.phone && <a href={"tel:" + service.phone}>{service.phone}</a>}</div>{service.emergency_service && <StatusBadge value="EMERGENCY" />}</article>)}</div>;
}

function AlertList() {
  const query = useQuery({ queryKey: ["alerts"], queryFn: () => api<Alert[]>("/alerts/active") });
  if (!query.data?.length) return <EmptyState title="No active alerts" copy="Your area has no active, server-published alerts." />;
  return <div className="record-list">{query.data.map((alert) => <article key={alert.id}><div className="record-icon warning"><AlertTriangle /></div><div><h3>{alert.title}</h3><p>{alert.message}</p></div><StatusBadge value={alert.severity} /></article>)}</div>;
}

function NotificationList() {
  const query = useQuery({ queryKey: ["notifications"], queryFn: () => api<Notification[]>("/notifications?limit=100") });
  if (!query.data?.length) return <EmptyState title="No notifications" copy="Important issue and emergency updates will be persisted here." />;
  return <div className="record-list">{query.data.map((item) => <article key={item.id}><div className="record-icon"><Bell /></div><div><h3>{item.title}</h3><p>{item.body}</p></div>{!item.read_at && <span className="new-dot">New</span>}</article>)}</div>;
}

function EmergencyList() {
  const query = useQuery({ queryKey: ["emergencies"], queryFn: () => api<Emergency[]>("/emergencies") });
  if (!query.data?.length) return <EmptyState title="No active SOS requests" copy="The response queue is clear." />;
  return <div className="record-list emergency-list">{query.data.map((item) => <article key={item.id}><div className="record-icon danger-icon"><Siren /></div><div><h3>{item.emergency_type}</h3><p>{item.address_text ?? "Precise coordinates available to responders"} · {new Date(item.created_at).toLocaleTimeString()}</p></div><StatusBadge value={item.status} /></article>)}</div>;
}

function UserList() {
  const query = useQuery({ queryKey: ["admin-users"], queryFn: () => api<Page<AdminUser>>("/admin/users?page_size=50") });
  if (!query.data?.items.length) return <EmptyState title="No users found" copy="Registered accounts will appear here." />;
  return <div className="user-table"><div className="table-head"><span>User</span><span>Role</span><span>Status</span><span>Joined</span></div>{query.data.items.map((user) => <article key={user.id}><div><strong>{user.full_name}</strong><small>{user.email}</small></div><span>{user.roles.join(", ")}</span><StatusBadge value={user.status} /><span>{new Date(user.created_at).toLocaleDateString()}</span></article>)}</div>;
}

function Overview({ role }: { role: Role }) {
  const issues = useQuery({ queryKey: ["issues", "overview", role], queryFn: () => api<Page<Issue>>("/issues?page_size=5" + (role === "CITIZEN" ? "&mine=true" : "")), enabled: role !== "RESPONDER" && role !== "ADMIN" });
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => api<Alert[]>("/alerts/active") });
  const emergencies = useQuery({ queryKey: ["emergencies"], queryFn: () => api<Emergency[]>("/emergencies"), enabled: role === "RESPONDER" });
  const users = useQuery({ queryKey: ["admin-users", "overview"], queryFn: () => api<Page<AdminUser>>("/admin/users?page_size=1"), enabled: role === "ADMIN" });
  const primaryCount = role === "RESPONDER" ? emergencies.data?.length : role === "ADMIN" ? users.data?.total : issues.data?.total;
  const primaryLabel = role === "RESPONDER" ? "Active SOS" : role === "ADMIN" ? "Registered people" : role === "AUTHORITY" ? "Issue queue" : "My reports";
  return <>
    <div className="metrics"><article><span>{primaryLabel}</span><strong>{primaryCount ?? "—"}</strong><small>Live municipal data</small></article><article><span>Active alerts</span><strong>{alerts.data?.length ?? "—"}</strong><small>Verified Kathmandu notices</small></article><article><span>Ward network</span><strong className="word-metric">32 wards</strong><small>Kathmandu Metropolitan City scope</small></article></div>
    <div className="workspace-grid"><section className="module-card"><div className="card-heading"><div><span className="eyebrow">Live workspace</span><h2>{role === "RESPONDER" ? "Emergency response queue" : role === "ADMIN" ? "Platform operations" : "Recent community activity"}</h2></div><CheckCircle2 /></div>{role === "RESPONDER" ? <EmergencyList /> : role === "ADMIN" ? <UserList /> : <IssueList mine={role === "CITIZEN"} />}</section><section className="command-card"><span className="eyebrow">Quick action</span><h2>{role === "CITIZEN" ? "Something needs attention?" : "Keep the community moving."}</h2><p>{role === "CITIZEN" ? "Create a location-aware report now or save it safely while offline." : "Open your operational queue to review the latest verified information."}</p><Link className="button light" href={role === "CITIZEN" ? "/citizen/report" : role === "RESPONDER" ? "/responder/emergencies" : role === "ADMIN" ? "/admin/users" : "/authority/issues"}>Open workspace <ArrowUpRight size={18} /></Link></section></div>
  </>;
}

const titles: Record<string, [string, string]> = {
  report: ["Report an issue", "Give your local team clear, useful information."],
  reports: ["My issue reports", "Track the status and history of every report you submitted."],
  issues: ["Community issue queue", "Verify, prioritize, and move local work forward."],
  map: ["Kathmandu operations map", "Search landmarks and explore nearby ward reports with OpenStreetMap context."],
  services: ["Civic service directory", "Find verified support and public services."],
  emergency: ["Emergency SOS", "Request immediate help with a server-confirmed alert."],
  emergencies: ["Emergency response board", "A mobile-first queue for active SOS incidents."],
  alerts: ["Active community alerts", "Only current notices published by authorized teams."],
  notifications: ["Notification center", "A persisted record of updates that matter to you."],
  users: ["People and access", "Manage account status and platform roles."],
  categories: ["Issue categories", "Maintain structural reporting categories."],
  areas: ["Administrative areas", "Define the geographic boundaries of operations."],
  audit: ["Audit trail", "Review privileged platform actions."],
};

export function RoleWorkspace({ role, slug }: { role: Role; slug: string[] }) {
  const section = slug[0] ?? "";
  const [title, description] = titles[section] ?? ["Command overview", "A live, role-specific view of your community operations."];
  let content: React.ReactNode = <Overview role={role} />;
  if (section === "report") content = <IssueReportForm />;
  if (section === "reports") content = <IssueList mine />;
  if (section === "issues") content = <IssueList />;
  if (section === "map") content = <MapCard />;
  if (section === "services") content = <ServiceList />;
  if (section === "emergency") content = <SOSPanel />;
  if (section === "emergencies") content = <EmergencyList />;
  if (section === "alerts") content = <AlertList />;
  if (section === "notifications") content = <NotificationList />;
  if (section === "users") content = <UserList />;
  if (["categories", "areas", "audit"].includes(section)) content = <EmptyState title={"No " + section + " records loaded"} copy="This screen intentionally waits for persisted API data and never fabricates dashboard content." />;
  return <DashboardShell role={role}><PageHeader eyebrow={role + " workspace"} title={title} description={description} />{content}</DashboardShell>;
}
