"use client";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { AuthApiError, login } from "@/lib/auth";
import AuthFrame from "@/components/AuthFrame";
function LoginForm() {
  const router=useRouter(); const searchParams=useSearchParams();
  const requestedNext=searchParams.get("next")||"/dashboard";
  const next=requestedNext.startsWith("/")&&!requestedNext.startsWith("//")&&!requestedNext.includes("\\")?requestedNext:"/dashboard";
  const [username,setUsername]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState<string|null>(null); const [loading,setLoading]=useState(false);
  async function submit(e:React.FormEvent) {e.preventDefault();setError(null);setLoading(true);try {await login(username.trim().toLowerCase(),password);router.push(next);router.refresh();}catch(err){setError(err instanceof AuthApiError?err.message:"Couldn't reach the server. Try again.");}finally{setLoading(false);}}
  return <AuthFrame><Link href="/" className="auth-back"><ArrowLeft size={13}/>Back to FraudLens</Link><h1>Welcome back.</h1><p>Sign in to your investigation workspace.</p><form onSubmit={submit} method="post"><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter your analyst username" autoComplete="username" required/></label><label>Password<input value={password} onChange={e=>setPassword(e.target.value)} type="password" placeholder="Enter your password" autoComplete="current-password" required/></label>{error&&<p className="form-error" role="alert">{error}</p>}<button className="primary-button" disabled={loading}>{loading?"Signing in…":"Open workspace"}<ArrowRight size={15}/></button></form><div className="auth-switch">New analyst? <Link href="/signup">Create an account</Link></div><aside className="demo-credentials"><strong>Explore the local demo</strong><p>Username <code>asharma</code> or <code>riyer</code><br/>Password <code>fraudlens123</code></p></aside></AuthFrame>;
}
export default function LoginPage(){return <Suspense><LoginForm/></Suspense>;}
