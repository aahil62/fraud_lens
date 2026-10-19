"use client";
import { useSyncExternalStore } from "react";
import { getStoredAnalyst } from "@/lib/auth";
const subscribe = () => () => {};
/** The signed-in analyst from local session storage (null during SSR). */
export function useAnalyst() {
  return useSyncExternalStore(subscribe, getStoredAnalyst, () => null);
}
export const initials = (name: string) =>
  name.split(/[ .]+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join("");
