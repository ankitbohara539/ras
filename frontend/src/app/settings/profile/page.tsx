"use client";

import { Accessibility, Languages, Save, UserRound } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { DashboardShell, PageHeader } from "@/components/dashboard/DashboardShell";
import { useAuth } from "@/features/auth/auth-context";
import {
  useReadingPreferences,
  type ReadingPreferences,
} from "@/features/preferences/reading-preferences";
import { ApiError, patch } from "@/lib/api/client";
import { primaryRole } from "@/lib/auth/roles";

const preferenceDefaults: ReadingPreferences = {
  language: "en",
  text_scale: "normal",
  high_contrast: false,
  reduced_motion: false,
  text_to_speech: false,
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const reading = useReadingPreferences();
  const profile = useForm<{ full_name: string; phone: string }>();
  const preferences = useForm<ReadingPreferences>({ defaultValues: preferenceDefaults });
  useEffect(() => {
    if (user) profile.reset({ full_name: user.full_name, phone: user.phone ?? "" });
  }, [profile, user]);

  useEffect(() => {
    preferences.reset(reading.preferences);
  }, [preferences, reading.preferences]);
  if (!user) return <main className="screen-loader">Loading profile...</main>;
  const role = primaryRole(user.roles);
  return (
    <DashboardShell role={role}>
      <PageHeader eyebrow="Personal settings" title="Profile & accessibility" description="Make CivicGrid comfortable and useful across devices and abilities." />
      <div className="settings-layout">
        <form className="module-card" onSubmit={profile.handleSubmit(async (values) => {
          try {
            await patch("/users/me", values);
            await refresh();
            toast.success("Profile updated.");
          } catch (error) {
            toast.error(errorMessage(error, "Unable to update your profile."));
          }
        })}>
          <div className="card-heading"><div><span className="eyebrow">Identity</span><h2>Profile details</h2></div><UserRound /></div>
          <div className="form-grid"><label className="field"><span>Full name</span><input {...profile.register("full_name", { required: true })} /></label><label className="field"><span>Phone</span><input {...profile.register("phone")} type="tel" /></label></div>
          <label className="field"><span>Email</span><input value={user.email} disabled /></label>
          <div className="read-only-row"><span>Assigned roles</span><strong>{user.roles.join(", ")}</strong></div>
          <button className="button primary fit" disabled={profile.formState.isSubmitting}><Save size={18} /> Save profile</button>
        </form>
        <form className="module-card" onSubmit={preferences.handleSubmit(async (values) => {
          try {
            const saved = await reading.save(values);
            preferences.reset(saved);
            await refresh();
            toast.success("Reading preferences saved and applied.");
          } catch (error) {
            toast.error(errorMessage(error, "Unable to save reading preferences."));
          }
        })}>
          <div className="card-heading"><div><span className="eyebrow">Inclusive access</span><h2>Reading preferences</h2></div><Accessibility /></div>
          {reading.error ? <p className="preference-error" role="alert">{reading.error}</p> : null}
          <div className="form-grid"><label className="field"><span><Languages size={15} /> Language</span><select {...preferences.register("language")}><option value="en">English</option><option value="ne">नेपाली</option></select></label><label className="field"><span>Text scale</span><select {...preferences.register("text_scale")}><option value="normal">Normal</option><option value="large">Large</option><option value="x-large">Extra large</option></select></label></div>
          <div className="toggle-list"><label><span><strong>High contrast</strong><small>Increase visual separation.</small></span><input {...preferences.register("high_contrast")} type="checkbox" /></label><label><span><strong>Reduced motion</strong><small>Minimize nonessential animation.</small></span><input {...preferences.register("reduced_motion")} type="checkbox" /></label><label><span><strong>Text to speech</strong><small>Enable supported reading controls.</small></span><input {...preferences.register("text_to_speech")} type="checkbox" /></label></div>
          <button className="button primary fit" disabled={reading.loading || preferences.formState.isSubmitting}><Save size={18} /> Save accessibility</button>
        </form>
      </div>
    </DashboardShell>
  );
}
