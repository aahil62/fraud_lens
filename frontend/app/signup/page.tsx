"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { AuthApiError, signup } from "@/lib/auth";
import AuthFrame from "@/components/AuthFrame";
export default function SignupPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signup(username.trim().toLowerCase(), displayName.trim(), password);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof AuthApiError ? err.message : "Couldn't reach the server. Try again.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <AuthFrame>
      <Link href="/" className="auth-back">
        <ArrowLeft size={13} />
        Back to FraudLens
      </Link>
      <h1>Your analyst workspace.</h1>
      <p>Create a local account. Every decision you make will carry your name.</p>
      <form onSubmit={submit} method="post">
        <label>
          Display name
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. N. Verma"
            autoComplete="name"
            required
          />
        </label>
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Choose an analyst username"
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="At least 6 characters"
            autoComplete="new-password"
            minLength={6}
            required
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="primary-button" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
          <ArrowRight size={15} />
        </button>
      </form>
      <div className="auth-switch">
        Already have access? <Link href="/login">Sign in</Link>
      </div>
    </AuthFrame>
  );
}
