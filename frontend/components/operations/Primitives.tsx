"use client";
import Link from "next/link";
import { ArrowsLeftRight, Bank, CreditCard, Tray, Money } from "@phosphor-icons/react";
import { channelName, human } from "@/lib/operations";
export function PageHeading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <Tray size={28} weight="duotone" />
      {children}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading-skeleton" role="status">
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <p className="sr-only">Loading the operational ledger…</p>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const risk = ["failed", "fraud", "critical", "high", "declined"].includes(value)
    ? "bad"
    : ["confirmed", "resolved", "posted", "released"].includes(value)
      ? "good"
      : "";
  return <span className={`status ${value} ${risk}`}>{human(value)}</span>;
}
export function ChannelLabel({ channel }: { channel: string }) {
  const Icon =
    channel === "upi"
      ? ArrowsLeftRight
      : channel === "net_banking"
        ? Bank
        : channel === "card"
          ? CreditCard
          : Money;
  return (
    <span className="channel-label">
      <Icon size={15} weight="duotone" />
      {channelName(channel)}
    </span>
  );
}
export function CaseLink({ id }: { id: string }) {
  return (
    <Link className="record-link" href={`/case?case_id=${encodeURIComponent(id)}`}>
      {id}
    </Link>
  );
}
