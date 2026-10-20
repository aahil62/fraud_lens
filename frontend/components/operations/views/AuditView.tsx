"use client";
import { useState } from "react";
import { human } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { Empty, Loading, PageHeading, Timeline } from "../Primitives";

export function AuditView() {
  const { snapshot } = useOperations();
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState("");
  if (!snapshot) return <Loading />;
  const eventTypes = [...new Set(snapshot.events.map((event) => event.event_type))];
  const needle = query.toLowerCase();
  const events = snapshot.events.filter((event) => {
    const text =
      `${event.id} ${event.event_type} ${event.message} ${event.case_id ?? ""} ${event.actor}`.toLowerCase();
    return text.includes(needle) && (!eventType || event.event_type === eventType);
  });
  return (
    <>
      <PageHeading
        title="Audit trail"
        description="Persisted event history with authenticated actors and ordered event identifiers."
      />
      <section className="ops-section audit-panel">
        <div className="filter-bar">
          <label className="audit-search">
            Search recent events
            <input
              placeholder="Case, event, message or analyst"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>
            Event type
            <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
              <option value="">All event types</option>
              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {human(type)}
                </option>
              ))}
            </select>
          </label>
          <p aria-live="polite">
            {events.length} of latest {snapshot.events.length} events · IST
          </p>
        </div>
        {events.length ? (
          <Timeline events={events} />
        ) : (
          <Empty>No events match these filters. Try a different case, actor or event type.</Empty>
        )}
      </section>
    </>
  );
}
