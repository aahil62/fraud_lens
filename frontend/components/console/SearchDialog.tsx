"use client";
import Link from "next/link";
import type { RefObject } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { channelName, money, type Snapshot } from "@/lib/operations";

type SearchDialogProps = {
  dialogRef: RefObject<HTMLDialogElement | null>;
  inputRef: RefObject<HTMLInputElement | null>;
  snapshot: Snapshot | null;
  query: string;
  onQueryChange: (query: string) => void;
};

/** A native dialog keeps keyboard focus and Escape behaviour; results cover the recent-case snapshot only. */
export function SearchDialog({ dialogRef, inputRef, snapshot, query, onQueryChange }: SearchDialogProps) {
  const close = () => dialogRef.current?.close();
  const results =
    snapshot?.cases
      .filter((item) =>
        `${item.case_id} ${item.account_id} ${channelName(item.channel)} ${item.verdict}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      )
      .slice(0, 8) ?? [];

  return (
    <dialog
      ref={dialogRef}
      className="search-dialog"
      aria-labelledby="search-heading"
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <h2 id="search-heading" className="sr-only">
        Search investigations
      </h2>
      <div className="search-dialog-header">
        <MagnifyingGlass size={21} />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Find a case, account or payment channel…"
          aria-label="Search cases"
        />
        <button onClick={close} aria-label="Close search">
          Esc
        </button>
      </div>
      <div className="search-results">
        {results.map((item) => (
          <Link href={`/case?case_id=${encodeURIComponent(item.case_id)}`} key={item.case_id} onClick={close}>
            <span>
              <strong>{item.case_id}</strong>
              <small>
                {channelName(item.channel)} · {item.account_id}
              </small>
            </span>
            <span className="numeric">{money(item.amount_minor)}</span>
          </Link>
        ))}
        {!results.length && <p>No matching investigations. Try an account reference or payment channel.</p>}
      </div>
      <div className="search-help">
        Searches the latest {snapshot?.cases.length ?? 0} investigations. Use the investigation queue for the
        complete ledger.
      </div>
    </dialog>
  );
}
