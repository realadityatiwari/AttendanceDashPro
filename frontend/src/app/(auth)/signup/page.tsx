"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Eye, EyeOff } from "lucide-react";

type FormErrors = {
  name?: string;
  rollNumber?: string;
  password?: string;
  confirmPassword?: string;
};

export default function SignupPage() {
  const [name, setName] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
    }
    if (confirmPassword !== password) {
      next.confirmPassword = "Passwords do not match.";
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
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), roll_number: rollNumber.trim(), password }),
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
      await refreshUser();
      router.push("/dashboard");
    } catch (err: any) {
      setServerError(err.message || "Unable to create account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
  const labelClass =
    "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground";

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8 shadow-sm">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Create Account</h1>
          <p className="mt-2 text-sm text-muted-foreground">AttendanceDash Pro V2</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          {(serverError || Object.values(errors).some(Boolean)) && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive">
              {serverError || Object.values(errors)[0]}
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="name" className={labelClass}>Full Name</label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => { setName(e.target.value); setErrors(prev => ({ ...prev, name: undefined })); }}
              placeholder="Your full name"
              className={inputClass}
            />
            {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="rollNumber" className={labelClass}>University Roll Number</label>
            <input
              id="rollNumber"
              type="text"
              inputMode="numeric"
              required
              value={rollNumber}
              onChange={(e) => { setRollNumber(e.target.value); setErrors(prev => ({ ...prev, rollNumber: undefined })); }}
              placeholder="13 digit roll number"
              className={inputClass}
            />
            {errors.rollNumber && <p className="text-xs text-destructive">{errors.rollNumber}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className={labelClass}>Password</label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors(prev => ({ ...prev, password: undefined })); }}
                placeholder="Min 8 characters"
                className={`${inputClass} pr-10`}
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
          </div>

          <div className="space-y-2">
            <label htmlFor="confirmPassword" className={labelClass}>Confirm Password</label>
            <div className="relative">
              <input
                id="confirmPassword"
                type={showConfirm ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setErrors(prev => ({ ...prev, confirmPassword: undefined })); }}
                placeholder="Re-enter password"
                className={`${inputClass} pr-10`}
              />
              <button
                type="button"
                aria-label={showConfirm ? "Hide password" : "Show password"}
                onClick={() => setShowConfirm(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground hover:text-foreground"
              >
                {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.confirmPassword && <p className="text-xs text-destructive">{errors.confirmPassword}</p>}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Login
          </Link>
        </p>
      </div>
    </div>
  );
}
