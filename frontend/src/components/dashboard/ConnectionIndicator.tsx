"use client";

import { Wifi, WifiOff } from "lucide-react";
import { useSyncExternalStore } from "react";
import {
  getRealtimeState,
  getServerRealtimeState,
  subscribeRealtime,
} from "@/lib/realtime/connection";

export function ConnectionIndicator() {
  const state = useSyncExternalStore(
    subscribeRealtime,
    getRealtimeState,
    getServerRealtimeState,
  );
  const connected = state === "CONNECTED";
  return (
    <span className={"connection " + (connected ? "online" : "offline")}>
      {connected ? <Wifi size={15} /> : <WifiOff size={15} />}
      {state === "CONNECTED" ? "Connected" : state === "RECONNECTING" ? "Reconnecting" : "Offline"}
    </span>
  );
}
