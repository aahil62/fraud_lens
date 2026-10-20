"use client";
import { useEffect, useState } from "react";
import { type Brief, type Case, getBrief, opsFetch } from "@/lib/operations";

/** Loads the case and its agent brief, refreshing both when the snapshot moves on. */
export function useCase(caseId: string, cursor: number | undefined) {
  const [item, setItem] = useState<Case | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!caseId) return;
    let active = true;
    void opsFetch<Case>(`/cases/${encodeURIComponent(caseId)}`)
      .then((value) => {
        if (active) {
          setItem(value);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Case unavailable.");
      });
    return () => {
      active = false;
    };
  }, [caseId, cursor]);
  const version = item?.version;
  useEffect(() => {
    if (!caseId || version === undefined) return;
    let active = true;
    void getBrief(caseId)
      .then((value) => {
        if (active) setBrief(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [caseId, version]);
  return { item, setItem, brief, error };
}
