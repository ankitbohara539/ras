export type RealtimeState = "CONNECTED" | "RECONNECTING" | "OFFLINE";

let currentState: RealtimeState = "RECONNECTING";

export function setRealtimeState(state: RealtimeState) {
  if (currentState === state) return;
  currentState = state;
  window.dispatchEvent(new Event("civic-realtime-state"));
}

export function subscribeRealtime(callback: () => void) {
  window.addEventListener("civic-realtime-state", callback);
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("civic-realtime-state", callback);
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

export function getRealtimeState(): RealtimeState {
  return navigator.onLine ? currentState : "OFFLINE";
}

export const getServerRealtimeState = (): RealtimeState => "RECONNECTING";
