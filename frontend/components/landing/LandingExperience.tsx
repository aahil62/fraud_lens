"use client";

import { useEffect, useRef, useState } from "react";
import type { ChannelKey } from "./channels";
import GoldenHour from "./GoldenHour";
import { Built } from "./sections/Built";
import { Channels } from "./sections/Channels";
import { Close } from "./sections/Close";
import { Hero, LandingNav } from "./sections/Hero";
import { Incident } from "./sections/Incident";
import { Team } from "./sections/Team";

type ScrollCraftWindow = Window & { ScrollCraft?: { mount: (root: HTMLElement) => { destroy: () => void } } };

export default function LandingExperience() {
  const rootRef = useRef<HTMLElement>(null);
  const [channelKey, setChannelKey] = useState<ChannelKey>("upi");
  const [stage, setStage] = useState(0);
  const [motionPaused, setMotionPaused] = useState(false);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    let canceled = false;
    let instance: { destroy: () => void } | undefined;
    async function mount() {
      // The scroll engine stays unchanged. Only decorative depth uses scroll
      // progress; essential text and controls have no entrance attributes.
      await import("./scrollcraft.js");
      if (!canceled && rootRef.current)
        instance = (window as ScrollCraftWindow).ScrollCraft?.mount(rootRef.current);
    }
    void mount();
    return () => {
      canceled = true;
      instance?.destroy();
    };
  }, []);

  /** Choosing a channel restarts the sample incident on that channel. */
  function selectChannel(key: ChannelKey) {
    setChannelKey(key);
    setStage(0);
    setResolved(false);
  }

  return (
    <main ref={rootRef} className="fl-landing">
      <a className="fl-skip" href="#sample-incident">
        Skip to the sample investigation
      </a>
      <div className="fl-opening">
        <LandingNav />
        <Hero
          channel={channelKey}
          motionPaused={motionPaused}
          onToggleMotion={() => setMotionPaused(!motionPaused)}
        />
      </div>
      <GoldenHour paused={motionPaused} />
      <Channels active={channelKey} onSelect={selectChannel} />
      <Incident
        channelKey={channelKey}
        stage={stage}
        resolved={resolved}
        onStage={setStage}
        onResolved={setResolved}
      />
      <Team />
      <Built />
      <Close />
    </main>
  );
}
