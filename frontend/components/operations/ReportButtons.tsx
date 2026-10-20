"use client";
import { useState } from "react";
import { DownloadSimple } from "@phosphor-icons/react";
import { exportReport } from "@/lib/operations";

export function ReportButtons({ caseId }: { caseId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function download(format: "json" | "markdown" | "pdf") {
    setBusy(true);
    setError("");
    try {
      await exportReport(caseId, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="button-row">
        {(["pdf", "markdown", "json"] as const).map((format) => (
          <button
            key={format}
            aria-label={`Download ${format.toUpperCase()} report for ${caseId}`}
            disabled={busy}
            onClick={() => {
              void download(format);
            }}
          >
            {format === "pdf" && <DownloadSimple size={13} />}{" "}
            {format === "markdown" ? "MD" : format.toUpperCase()}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </div>
  );
}
