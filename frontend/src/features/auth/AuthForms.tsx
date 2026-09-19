"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Eye, EyeOff, KeyRound, LoaderCircle, LockKeyhole, MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Brand } from "@/components/Brand";
import { PublicLanguageToggle, usePublicLanguage } from "@/features/i18n/public-language";
import { ApiError, post } from "@/lib/api/client";
import { primaryRole, rolePath } from "@/lib/auth/roles";
import { useAuth } from "./auth-context";

const password = z
  .string()
  .min(8, "Use at least 8 characters.")
  .max(128)
  .regex(/[A-Z]/, "Add an uppercase letter.")
  .regex(/[a-z]/, "Add a lowercase letter.")
  .regex(/\d/, "Add a number.");
const loginSchema = z.object({ email: z.email(), password: z.string().min(1) });
const developmentAccounts = [
  { role: "Admin", email: "admin@demo.civicgrid.dev", password: "CivicGridAdmin@2026!" },
  { role: "Authority", email: "authority@demo.civicgrid.dev", password: "CivicGridAuthority@2026!" },
  { role: "Responder", email: "responder@demo.civicgrid.dev", password: "CivicGridResponder@2026!" },
  { role: "Citizen", email: "citizen@demo.civicgrid.dev", password: "CivicGridCitizen@2026!" },
] as const;
const registerSchema = z
  .object({
    full_name: z.string().trim().min(2).max(120),
    email: z.email(),
    password,
    confirm_password: z.string(),
    terms: z.literal(true, { error: "Accept the terms to continue." }),
  })
  .refine((value) => value.password === value.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match.",
  });

function AuthFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { text } = usePublicLanguage();
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow">{text("Kathmandu's connected wards", "काठमाडौंका जोडिएका वडाहरू")}</span>
          <h1>{text("Local action,", "स्थानीय काम,")}<br />{text("made visible.", "सबैलाई देखिने।")}</h1>
          <p>{text("Report ward issues, find nearby civic help, and stay connected when every minute counts.", "वडाका समस्या रिपोर्ट गर्नुहोस्, नजिकको नागरिक सेवा खोज्नुहोस् र हरेक महत्त्वपूर्ण समयमा जोडिरहनुहोस्।")}</p>
        </div>
        <p className="story-foot">{text("Accessible · Privacy-minded · Built for low connectivity", "पहुँचयोग्य · गोपनीय · कमजोर इन्टरनेटमैत्री")}</p>
      </section>
      <section className="auth-panel">
        <div className="auth-mobile-brand"><Brand /></div>
        <div className="auth-card">
          <div className="auth-card-tools"><span className="eyebrow">{text("Secure community access", "सुरक्षित नागरिक पहुँच")}</span><PublicLanguageToggle compact /></div>
          <h2>{title}</h2>
          <p className="muted">{description}</p>
          {children}
        </div>
      </section>
    </main>
  );
}

function PasswordField({ registration, error }: { registration: object; error?: string }) {
  const [shown, setShown] = useState(false);
  const { text } = usePublicLanguage();
  return (
    <label className="field">
      <span>{text("Password", "पासवर्ड")}</span>
      <span className="input-icon">
        <LockKeyhole size={17} />
        <input
          {...registration}
          type={shown ? "text" : "password"}
          autoComplete="current-password"
        />
        <button type="button" onClick={() => setShown(!shown)} aria-label="Toggle password visibility">
          {shown ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </span>
      {error && <small role="alert">{error}</small>}
    </label>
  );
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

export function LoginForm() {
  const { text } = usePublicLanguage();
  const router = useRouter();
  const { login } = useAuth();
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const selectDevelopmentAccount = (account: (typeof developmentAccounts)[number]) => {
    form.setValue("email", account.email, { shouldDirty: true, shouldValidate: true });
    form.setValue("password", account.password, { shouldDirty: true, shouldValidate: true });
    form.clearErrors();
    setSelectedRole(account.role);
  };
  const submit = form.handleSubmit(async (values) => {
    try {
      const user = await login(values);
      router.replace(rolePath(primaryRole(user.roles)));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });
  return (
    <AuthFrame title={text("Welcome back", "स्वागत छ")} description={text("Sign in to your Kathmandu civic command center.", "काठमाडौं नागरिक कमाण्ड केन्द्रमा साइन इन गर्नुहोस्।")}>
      <>
        <form className="form-stack" onSubmit={submit} noValidate>
          <label className="field">
            <span>{text("Email address", "इमेल ठेगाना")}</span>
            <span className="input-icon"><MailCheck size={17} /><input {...form.register("email")} type="email" autoComplete="email" /></span>
            {form.formState.errors.email && <small>{form.formState.errors.email.message}</small>}
          </label>
          <PasswordField registration={form.register("password")} error={form.formState.errors.password?.message} />
          <div className="form-between"><span>{text("Protected with rotating sessions", "सुरक्षित सत्रद्वारा संरक्षित")}</span><Link href="/forgot-password">{text("Forgot password?", "पासवर्ड बिर्सनुभयो?")}</Link></div>
          <button className="button primary" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? <LoaderCircle className="spin" /> : <>{text("Sign in", "साइन इन")} <ArrowRight size={18} /></>}
          </button>
          <p className="form-foot">{text("New to CivicGrid?", "CivicGrid मा नयाँ हुनुहुन्छ?")} <Link href="/register">{text("Create an account", "खाता बनाउनुहोस्")}</Link></p>
        </form>
        {process.env.NODE_ENV === "development" ? (
          <aside className="development-credentials" aria-label="Development login accounts">
            <div className="development-credentials-heading">
              <KeyRound size={16} />
              <div><strong>Role preview accounts</strong><small>{selectedRole ? `${selectedRole} account is ready to sign in.` : "Choose a role to securely fill the login form."}</small></div>
            </div>
            <div className="development-account-list">
              {developmentAccounts.map((account) => (
                <button
                  type="button"
                  key={account.role}
                  className={selectedRole === account.role ? "selected" : ""}
                  onClick={() => selectDevelopmentAccount(account)}
                  aria-label={`Use ${account.role} development account`}
                  aria-pressed={selectedRole === account.role}
                >
                  <span>{account.role}{selectedRole === account.role ? " · Ready" : ""}</span>
                  <code>{account.email}</code>
                  <small>Password <b aria-hidden="true">••••••••••••</b></small>
                </button>
              ))}
            </div>
            <p className="development-note">Local development only · Passwords stay masked and are filled directly into the protected form.</p>
          </aside>
        ) : null}
      </>
    </AuthFrame>
  );
}

export function RegisterForm() {
  const { text } = usePublicLanguage();
  const router = useRouter();
  const { register: createAccount } = useAuth();
  const form = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema) });
  const submit = form.handleSubmit(async (values) => {
    try {
      await createAccount({
        full_name: values.full_name,
        email: values.email,
        password: values.password,
        confirm_password: values.confirm_password,
      });
      toast.success("Account created. You can sign in now.");
      router.push("/login");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });
  return (
    <AuthFrame title={text("Join your community", "आफ्नो समुदायमा जोडिनुहोस्")} description={text("Citizen accounts are created with the safest default role.", "नागरिक खाता सुरक्षित पूर्वनिर्धारित भूमिकासहित बनाइन्छ।")}>
      <form className="form-stack" onSubmit={submit} noValidate>
        <label className="field"><span>{text("Full name", "पूरा नाम")}</span><input {...form.register("full_name")} autoComplete="name" />{form.formState.errors.full_name && <small>{form.formState.errors.full_name.message}</small>}</label>
        <label className="field"><span>{text("Email address", "इमेल ठेगाना")}</span><input {...form.register("email")} type="email" autoComplete="email" />{form.formState.errors.email && <small>{form.formState.errors.email.message}</small>}</label>
        <PasswordField registration={form.register("password")} error={form.formState.errors.password?.message} />
        <label className="field"><span>{text("Confirm password", "पासवर्ड पुष्टि")}</span><input {...form.register("confirm_password")} type="password" autoComplete="new-password" />{form.formState.errors.confirm_password && <small>{form.formState.errors.confirm_password.message}</small>}</label>
        <label className="check"><input {...form.register("terms")} type="checkbox" /> <span>I agree to responsible use and the privacy policy.</span></label>
        {form.formState.errors.terms && <small className="field-error">{form.formState.errors.terms.message}</small>}
        <button className="button primary" disabled={form.formState.isSubmitting}>{text("Create citizen account", "नागरिक खाता बनाउनुहोस्")} <ArrowRight size={18} /></button>
        <p className="form-foot">{text("Already registered?", "पहिले नै दर्ता हुनुहुन्छ?")} <Link href="/login">{text("Sign in", "साइन इन")}</Link></p>
      </form>
    </AuthFrame>
  );
}

export function ForgotPasswordForm() {
  const { text } = usePublicLanguage();
  const form = useForm<{ email: string }>({ defaultValues: { email: "" } });
  const [sent, setSent] = useState(false);
  const submit = form.handleSubmit(async (values) => {
    await post("/auth/forgot-password", values);
    setSent(true);
  });
  return (
    <AuthFrame title={text("Reset access", "पहुँच पुनःस्थापना")} description={text("We use a generic response to keep account details private.", "खाता विवरण गोप्य राख्न हामी सामान्य प्रतिक्रिया प्रयोग गर्छौं।")}>
      {sent ? <div className="confirmation"><MailCheck size={42} /><p>If an account exists, reset instructions are on the way.</p><Link href="/login">Return to sign in</Link></div> : <form className="form-stack" onSubmit={submit}><label className="field"><span>Email address</span><input {...form.register("email")} type="email" required /></label><button className="button primary">Send reset link</button></form>}
    </AuthFrame>
  );
}

export function ResetPasswordForm({ token }: { token?: string }) {
  const { text } = usePublicLanguage();
  const form = useForm<{ password: string; confirm_password: string }>();
  const router = useRouter();
  const submit = form.handleSubmit(async (values) => {
    if (!token) return toast.error("This reset link is missing its token.");
    try {
      await post("/auth/reset-password", { ...values, token });
      toast.success("Password updated.");
      router.replace("/login");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  });
  return (
    <AuthFrame title={text("Choose a new password", "नयाँ पासवर्ड छान्नुहोस्")} description={text("All existing sessions will be revoked.", "सबै पुराना सत्रहरू बन्द हुनेछन्।")}>
      <form className="form-stack" onSubmit={submit}><PasswordField registration={form.register("password")} /><label className="field"><span>Confirm password</span><input {...form.register("confirm_password")} type="password" /></label><button className="button primary">Update password</button></form>
    </AuthFrame>
  );
}
