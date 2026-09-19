"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { setRealtimeState } from "@/lib/realtime/connection";
import type { Notification } from "@/types";

export function NotificationBell({ home }: { home: string }) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const count = useQuery({ queryKey: ["notifications", "count"], queryFn: () => api<{ count: number }>("/notifications/unread-count") });
  const recent = useQuery({ queryKey: ["notifications"], queryFn: () => api<Notification[]>("/notifications?limit=5"), enabled: open });
  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_WS_URL;
    if (!url) return;
    let socket: WebSocket | undefined;
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    let attempts = 0;
    const connect = () => {
      if (stopped || !navigator.onLine) {
        setRealtimeState("OFFLINE");
        return;
      }
      setRealtimeState("RECONNECTING");
      socket = new WebSocket(url);
      socket.onopen = () => {
        attempts = 0;
        setRealtimeState("CONNECTED");
        // Persisted notifications reconcile anything missed while disconnected.
        void client.invalidateQueries({ queryKey: ["notifications"] });
      };
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.event === "system.ping") socket?.send("system.pong");
        else {
          void client.invalidateQueries({ queryKey: ["notifications"] });
          if (payload.event?.startsWith("issue.")) void client.invalidateQueries({ queryKey: ["issues"] });
          if (payload.event?.startsWith("emergency.")) void client.invalidateQueries({ queryKey: ["emergencies"] });
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (stopped) return;
        setRealtimeState(navigator.onLine ? "RECONNECTING" : "OFFLINE");
        const backoff = Math.min(30_000, 1_000 * 2 ** Math.min(attempts++, 5));
        const jitter = Math.floor(Math.random() * 500);
        timer = setTimeout(connect, backoff + jitter);
      };
    };
    connect();
    return () => { stopped = true; clearTimeout(timer); socket?.close(); };
  }, [client]);
  return (
    <div className="notification-wrap">
      <button className="icon-button" onClick={() => setOpen(!open)} aria-label="Notifications"><Bell size={19} />{Boolean(count.data?.count) && <b>{count.data?.count}</b>}</button>
      {open && <div className="notification-popover"><header><strong>Notifications</strong><span>{count.data?.count ?? 0} unread</span></header>{recent.isLoading ? <p className="muted">Loading updates…</p> : recent.data?.length ? recent.data.map((item) => <article key={item.id}><i className={item.read_at ? "" : "unread"} /><div><strong>{item.title}</strong><p>{item.body}</p></div></article>) : <p className="muted">You are all caught up.</p>}<Link href={home + "/notifications"}>View notification center</Link></div>}
    </div>
  );
}
