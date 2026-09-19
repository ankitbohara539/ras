"use client";

import { Crosshair, PhoneCall, ShieldAlert, Siren } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { post } from "@/lib/api/client";

export function SOSPanel() {
  const [type, setType] = useState("MEDICAL");
  const [message, setMessage] = useState("");
  const [coordinates, setCoordinates] = useState<{ latitude: number; longitude: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const locate = () => navigator.geolocation.getCurrentPosition(
    ({ coords }) => setCoordinates({ latitude: coords.latitude, longitude: coords.longitude }),
    () => toast.error("Share a location before sending SOS."),
    { enableHighAccuracy: true, timeout: 10_000 },
  );
  const send = async () => {
    if (!navigator.onLine) {
      toast.error("Emergency request has NOT reached the server.");
      return;
    }
    if (!coordinates) return toast.error("Add your current location first.");
    if (!window.confirm("Send this emergency SOS to verified responders now?")) return;
    setBusy(true);
    try {
      await post("/emergencies/sos", { emergency_type: type, message, ...coordinates });
      toast.success("SOS saved by the server. Keep this page open for live updates.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Emergency request was not confirmed.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="sos-card">
      <div className="sos-icon"><Siren /></div>
      <div><span className="eyebrow danger-text">Emergency channel</span><h2>Request immediate help</h2><p>Only a server-confirmed request is shown as sent. Offline SOS is never silently queued.</p></div>
      <div className="sos-fields"><label className="field"><span>Emergency type</span><select value={type} onChange={(event) => setType(event.target.value)}><option>MEDICAL</option><option>FIRE</option><option>SAFETY</option><option>DISASTER</option><option>OTHER</option></select></label><label className="field"><span>Short message (optional)</span><textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></label></div>
      <button className="button secondary" onClick={locate}><Crosshair size={18} /> {coordinates ? "Location captured" : "Share current location"}</button>
      <button className="button danger-button" onClick={send} disabled={busy}><ShieldAlert size={19} /> {busy ? "Contacting responders…" : "Send emergency SOS"}</button>
      <div className="emergency-contact"><PhoneCall size={18} /><span>If data service is unavailable, call your verified local emergency number directly.</span></div>
    </section>
  );
}
