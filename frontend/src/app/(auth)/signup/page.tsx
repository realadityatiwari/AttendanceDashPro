"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Eye, EyeOff } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

type FormErrors = {
  name?: string;
  rollNumber?: string;
  password?: string;
  confirmPassword?: string;
  electiveI?: string;
  electiveII?: string;
};

// Department Elective options for registration. The backend contract requires
// both selections (POST /auth/register validates them authoritatively against
// the active semester's DB catalog — subjects.elective_slot — and rejects an
// unknown code with a 422 detail this page surfaces). There is intentionally
// no pre-auth catalog endpoint, so this client-side list mirrors the deployed
// semester's catalog; it is NOT presented as a hardcoded section assumption.
const ELECTIVE_I_OPTIONS = [
  { code: "BCS-052", name: "Data Analytics" },
  { code: "BCS-053", name: "Computer Graphics" },
  { code: "BCS-054", name: "OOS Design with C++" },
];

const ELECTIVE_II_OPTIONS = [
  { code: "BCS-055", name: "Machine Learning Techniques" },
  { code: "BCS-056", name: "Application of Soft Computing" },
  { code: "BCS-058", name: "Data Warehousing & Data Mining" },
];

export default function SignupPage() {
  const [name, setName] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [electiveI, setElectiveI] = useState("");
  const [electiveII, setElectiveII] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);
  const { refreshUser } = useAuth();
  const router = useRouter();

  const validate = (): boolean => {
    const next: FormErrors = {};
    if (!name.trim()) next.name = "Full name is required.";
    if (!/^\d{13}$/.test(rollNumber.trim())) {
      next.rollNumber = "Roll number must be 13 digits.";
    }
    if (password.length < 8) {
      next.password = "Password must be at least 8 characters.";
    } else if (password.length > 128) {
      next.password = "Password must not exceed 128 characters.";
    } else if (!/[A-Za-z]/.test(password)) {
      next.password = "Password must contain at least one letter.";
    } else if (!/[0-9]/.test(password)) {
      next.password = "Password must contain at least one digit.";
    }
    if (confirmPassword !== password) {
      next.confirmPassword = "Passwords do not match.";
    }
    if (!electiveI) {
      next.electiveI = "Please select a Department Elective-I.";
    }
    if (!electiveII) {
      next.electiveII = "Please select a Department Elective-II.";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");
    if (!validate()) return;
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: "POST",
        // Phase 25.2: credentials are included so the backend's HttpOnly
        // refresh cookie (Set-Cookie on the register response) is stored by
        // the browser for the cross-origin architecture. JSON contract
        // unchanged.
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          roll_number: rollNumber.trim(),
          password,
          elective_i: electiveI,
          elective_ii: electiveII,
        }),
      });

      if (!response.ok) {
        let detail: unknown = null;
        try {
          const errorData = await response.json();
          detail = errorData.detail;
        } catch {}
        if (response.status === 409) {
          throw new Error("An account with this roll number already exists.");
        }
        if (response.status === 422 && typeof detail === "string") {
          throw new Error(detail);
        }
        throw new Error("Unable to create account. Please try again.");
      }

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);

      // Authenticate through the existing flow, then enter the app shell.
      // A transient profile fetch failure must not block navigation — the
      // session token is already stored and the shell retries through SWR.
      try {
        await refreshUser();
      } catch {
        // Profile refresh failed transiently; navigate anyway.
      }
      router.push("/dashboard");
    } catch (err) {
      // Network-level failures surface as TypeError with the browser's raw
      // "Failed to fetch" — replace it with an actionable message. HTTP
      // errors (4xx/5xx) keep their backend-provided detail.
      if (err instanceof TypeError) {
        setServerError("Unable to reach the server. Check your connection and try again.");
      } else if (err instanceof Error && err.message) {
        setServerError(err.message);
      } else {
        setServerError("Unable to create account. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const labelClass =
    "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground";

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8 shadow-sm">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Create Account</h1>
          <p className="mt-2 text-sm text-muted-foreground">AttendanceDash Pro</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          {(serverError || Object.values(errors).some(Boolean)) && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive">
              {serverError || Object.values(errors)[0]}
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="name" className={labelClass}>Full Name</label>
            <Input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => { setName(e.target.value); setErrors(prev => ({ ...prev, name: undefined })); }}
              placeholder="Your full name"
            />
            {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="rollNumber" className={labelClass}>University Roll Number</label>
            <Input
              id="rollNumber"
              type="text"
              inputMode="numeric"
              required
              value={rollNumber}
              onChange={(e) => { setRollNumber(e.target.value); setErrors(prev => ({ ...prev, rollNumber: undefined })); }}
              placeholder="13 digit roll number"
            />
            {errors.rollNumber && <p className="text-xs text-destructive">{errors.rollNumber}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className={labelClass}>Password</label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors(prev => ({ ...prev, password: undefined })); }}
                placeholder="Min 8 characters"
                className="pr-10"
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="confirmPassword" className={labelClass}>Confirm Password</label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirm ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setErrors(prev => ({ ...prev, confirmPassword: undefined })); }}
                placeholder="Re-enter password"
                className="pr-10"
              />
              <button
                type="button"
                aria-label={showConfirm ? "Hide password" : "Show password"}
                onClick={() => setShowConfirm(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md"
              >
                {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.confirmPassword && <p className="text-xs text-destructive">{errors.confirmPassword}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="electiveI" className={labelClass}>Department Elective-I</label>
            <Select
              id="electiveI"
              value={electiveI}
              onChange={(e) => { setElectiveI(e.target.value); setErrors(prev => ({ ...prev, electiveI: undefined })); }}
              required
            >
              <option value="">Select Elective-I</option>
              {ELECTIVE_I_OPTIONS.map(o => (
                <option key={o.code} value={o.code}>{o.code} — {o.name}</option>
              ))}
            </Select>
            {errors.electiveI && <p className="text-xs text-destructive">{errors.electiveI}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="electiveII" className={labelClass}>Department Elective-II</label>
            <Select
              id="electiveII"
              value={electiveII}
              onChange={(e) => { setElectiveII(e.target.value); setErrors(prev => ({ ...prev, electiveII: undefined })); }}
              required
            >
              <option value="">Select Elective-II</option>
              {ELECTIVE_II_OPTIONS.map(o => (
                <option key={o.code} value={o.code}>{o.code} — {o.name}</option>
              ))}
            </Select>
            {errors.electiveII && <p className="text-xs text-destructive">{errors.electiveII}</p>}
            {/* UI-028: honest framing — the options mirror the current
                semester's catalog and the server is authoritative. */}
            <p className="text-xs text-muted-foreground">
              Elective options reflect the current semester&apos;s catalog; the
              server verifies your selection against it.
            </p>
          </div>

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Creating account..." : "Create Account"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
