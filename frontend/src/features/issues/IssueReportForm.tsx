"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Crosshair, LoaderCircle, Save, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { api, post } from "@/lib/api/client";
import type { Issue } from "@/types";
import { queueIssue, syncQueuedIssues } from "@/lib/storage/offline-queue";

type Report = {
  category_id: string;
  administrative_area_id?: string;
  title: string;
  description: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  latitude: number;
  longitude: number;
  address_text?: string;
  anonymous_public_display: boolean;
};

type Ward = { id: string; code: string; name: string };
type ReverseResult = { display_name: string; ward: string | null };

export function IssueReportForm() {
  const client = useQueryClient();
  const [locating, setLocating] = useState(false);
  const [media, setMedia] = useState<File[]>([]);
  const categories = useQuery({ queryKey: ["issue-categories"], queryFn: () => api<{ id: string; name: string }[]>("/issues/categories") });
  const wards = useQuery({ queryKey: ["kathmandu-wards"], queryFn: () => api<Ward[]>("/geo/wards") });
  const form = useForm<Report>({ defaultValues: { severity: "MEDIUM", anonymous_public_display: false, latitude: 27.7172, longitude: 85.324 } });
  useEffect(() => {
    const sync = () => void syncQueuedIssues();
    window.addEventListener("online", sync);
    void syncQueuedIssues();
    return () => window.removeEventListener("online", sync);
  }, []);
  const locate = () => {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        form.setValue("latitude", Number(coords.latitude.toFixed(7)));
        form.setValue("longitude", Number(coords.longitude.toFixed(7)));
        try {
          const place = await api<ReverseResult>(`/geo/reverse?lat=${coords.latitude}&lng=${coords.longitude}`);
          if (place.display_name) form.setValue("address_text", place.display_name, { shouldDirty: true });
        } catch {
          toast.info("Coordinates captured. Add a nearby landmark if the address lookup is unavailable.");
        }
        setLocating(false);
      },
      () => {
        toast.error("Location was not shared. You can enter coordinates manually.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };
  const submit = form.handleSubmit(async (values) => {
    const payload = { ...values, client_request_id: crypto.randomUUID() };
    if (!navigator.onLine) {
      await queueIssue({ ...payload, media });
      toast.success("Saved offline. CivicGrid will sync this report when you reconnect.");
      form.reset();
      setMedia([]);
      return;
    }
    try {
      const created = await post<Issue>("/issues", payload);
      for (const file of media) {
        const body = new FormData();
        body.append("file", file);
        await api("/issues/" + created.id + "/media", { method: "POST", body });
      }
      await client.invalidateQueries({ queryKey: ["issues"] });
      toast.success("Issue reported and saved by the server.");
      form.reset();
      setMedia([]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not submit this report.");
    }
  });
  return (
    <form className="module-card report-form" onSubmit={submit}>
      <div className="form-grid">
        <label className="field"><span>Issue category</span><select {...form.register("category_id", { required: true })}><option value="">Choose a category</option>{categories.data?.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label className="field"><span>Suggested severity</span><select {...form.register("severity")}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label>
      </div>
      <label className="field"><span>Kathmandu ward</span><select {...form.register("administrative_area_id")}><option value="">Select the ward if known</option>{wards.data?.map((ward) => <option key={ward.id} value={ward.id}>{ward.name}</option>)}</select></label>
      <label className="field"><span>Short title</span><input {...form.register("title", { required: true, minLength: 4 })} placeholder="What needs attention?" /></label>
      <label className="field"><span>What is happening?</span><textarea {...form.register("description", { required: true, minLength: 10 })} rows={5} placeholder="Share useful details for the response team." /></label>
      <div className="location-panel">
        <div><strong>Pin the location</strong><p>Location helps route this report. It is requested only when you choose.</p></div>
        <button className="button secondary" type="button" onClick={locate}>{locating ? <LoaderCircle className="spin" /> : <Crosshair size={18} />} Use my location</button>
        <div className="coordinate-grid"><label className="field"><span>Latitude</span><input {...form.register("latitude", { valueAsNumber: true })} type="number" step="any" /></label><label className="field"><span>Longitude</span><input {...form.register("longitude", { valueAsNumber: true })} type="number" step="any" /></label></div>
      </div>
      <label className="field"><span>Nearby address or landmark</span><input {...form.register("address_text")} placeholder="Example: near the ward office, temple, chowk, or street" /></label>
      <label className="field"><span>Photos (JPEG, PNG, or WebP; up to 5)</span><input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => setMedia(Array.from(event.target.files ?? []).slice(0, 5))} /></label>
      <label className="check"><input {...form.register("anonymous_public_display")} type="checkbox" /><span>Hide my identity on public issue views</span></label>
      <div className="offline-note"><WifiOff size={18} /><span>When offline, non-emergency reports are stored on this device with a unique request ID and synced later.</span></div>
      <button className="button primary fit" disabled={form.formState.isSubmitting}><Save size={18} /> Submit report</button>
    </form>
  );
}
