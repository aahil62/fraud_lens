import type { KeyboardEvent } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bank,
  CreditCard,
  Fingerprint,
  MagnifyingGlass,
} from "@phosphor-icons/react";
import { channels, type ChannelKey } from "../channels";

const channelIcons = [Fingerprint, Bank, CreditCard, Bank];

export function Channels({ active, onSelect }: { active: ChannelKey; onSelect: (key: ChannelKey) => void }) {
  const channel = channels.find((item) => item.key === active)!;

  /** Vertical tab list: arrows move and select, Home/End jump to the ends. */
  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (index + 1) % channels.length;
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft")
      next = (index + channels.length - 1) % channels.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = channels.length - 1;
    else return;
    event.preventDefault();
    onSelect(channels[next].key);
    document.getElementById(`rail-tab-${channels[next].key}`)?.focus();
  }

  return (
    <section
      className="fl-rails fl-section"
      id="payment-rails"
      data-sc-act="flow"
      aria-labelledby="rails-heading"
    >
      <div className="fl-rails-heading">
        <h2 id="rails-heading">
          Different rails.
          <br />
          <span>One line of sight.</span>
        </h2>
        <p>
          Context changes from channel to channel.
          <br />
          The need for a clear decision doesn’t.
        </p>
        <a className="fl-text-link" href="#sample-incident">
          Trace an example <ArrowRight size={18} />
        </a>
      </div>
      <div className="fl-channel-surface">
        <div
          className="fl-channel-tabs"
          role="tablist"
          aria-label="Payment channel"
          aria-orientation="vertical"
        >
          {channels.map((item, index) => {
            const Icon = channelIcons[index];
            const selected = active === item.key;
            return (
              <button
                type="button"
                role="tab"
                key={item.key}
                id={`rail-tab-${item.key}`}
                aria-controls={`rail-panel-${item.key}`}
                aria-selected={selected}
                tabIndex={selected ? 0 : -1}
                onKeyDown={(event) => tabKey(event, index)}
                onClick={() => onSelect(item.key)}
              >
                <Icon size={22} weight={selected ? "fill" : "regular"} />
                <span>{item.name}</span>
                <ArrowUpRight size={17} />
              </button>
            );
          })}
        </div>
        <div
          className="fl-channel-story"
          role="tabpanel"
          id={`rail-panel-${active}`}
          aria-labelledby={`rail-tab-${active}`}
          tabIndex={0}
        >
          <div className="fl-channel-trace" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
            <i>
              <MagnifyingGlass size={21} />
            </i>
            <span />
            <span />
          </div>
          <h3>{channel.detail}</h3>
          <p>{channel.description}</p>
          <span className="fl-channel-caption">
            Explore {channel.name} in the sample below <ArrowRight size={14} />
          </span>
        </div>
      </div>
    </section>
  );
}
