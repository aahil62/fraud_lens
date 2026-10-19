"use client";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import { AuthApiError, login } from "@/lib/auth";
import AuthFrame from "@/components/AuthFrame";
const DEMO_ROLES = [
  { username: "kmehta", label: "Continue as L1 Analyst (K. Mehta)" },
  { username: "riyer", label: "Continue as L2 Senior Analyst (R. Iyer)" },
  { username: "asharma", label: "Continue as Fraud Supervisor (A. Sharma)" },
];
function LoginForm() {
  const router=useRouter(); const searchParams=useSearchParams();
  const requestedNext=searchParams.get("next")||"/dashboard";
  const next=requestedNext.startsWith("/")&&!requestedNext.startsWith("//")&&!requestedNext.includes("\\")?requestedNext:"/dashboard";
  const [username,setUsername]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState<string|null>(null); const [loading,setLoading]=useState(false);
  const demo=process.env.NEXT_PUBLIC_DEMO_MODE==="1";
  async function signIn(name:string,secret:string) {setError(null);setLoading(true);try {await login(name.trim().toLowerCase(),secret);router.push(next);router.refresh();}catch(err){setError(err instanceof AuthApiError?err.message:"Couldn't reach the server. Try again.");}finally{setLoading(false);}}
  async function submit(e:React.FormEvent) {e.preventDefault();await signIn(username,password);}
  return <AuthFrame><Link href="/" className="auth-back"><ArrowLeft size={13}/>Back to FraudLens</Link><h1>Welcome back.</h1><p>Sign in to your investigation workspace.</p><form onSubmit={submit} method="post"><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter your analyst username" autoComplete="username" required/></label><label>Password<input value={password} onChange={e=>setPassword(e.target.value)} type="password" placeholder="Enter your password" autoComplete="current-password" required/></label>{error&&<p className="form-error" role="alert">{error}</p>}<button className="primary-button" disabled={loading}>{loading?"Signing in…":"Open workspace"}<ArrowRight size={15}/></button></form>{process.env.NEXT_PUBLIC_PUBLIC_DEMO!=="1"&&<div className="auth-switch">New analyst? <Link href="/signup">Create an account</Link></div>}{demo&&<aside className="demo-credentials demo-roles" aria-label="Demo roles"><strong>Try a demo role</strong>{DEMO_ROLES.map(role=><button key={role.username} type="button" disabled={loading} onClick={()=>{void signIn(role.username,"fraudlens123");}}>{role.label}<ArrowRight size={14} aria-hidden="true"/></button>)}<p>Open two windows with different roles to see the hand-off live.</p></aside>}</AuthFrame>;
}
export default function LoginPage(){return <Suspense><LoginForm/></Suspense>;}
