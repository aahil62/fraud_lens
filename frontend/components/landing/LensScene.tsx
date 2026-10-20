"use client";

import { useEffect, useRef, useState } from "react";
import type * as Three from "three";
import type { ChannelKey } from "./channels";
import { buildLensModel, disposeScene } from "./lensModel";
import { LensPoster } from "./LensPoster";

const channelOrder: ChannelKey[] = ["upi", "netbanking", "card", "atm"];

/** True when WebGL is missing or runs in software (no GPU): the scene would then
 * render every frame on the main thread, so the static lens is the better page. */
function softwareWebGL() {
  const gl =
    document.createElement("canvas").getContext("webgl2") ??
    document.createElement("canvas").getContext("webgl");
  if (!gl) return true;
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  const rendererName = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
  // Free the probe's context now; browsers cap how many can be live at once.
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  return /swiftshader|llvmpipe|software|basic render/i.test(rendererName);
}

export default function LensScene({ channel, animated = true }: { channel: ChannelKey; animated?: boolean }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef(channel);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    activeRef.current = channel;
  }, [channel]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !animated) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let disposed = false;
    let generation = 0;
    let stopScene: (() => void) | undefined;

    async function createScene() {
      const ticket = ++generation;
      if (motion.matches || disposed || !host || softwareWebGL()) return;
      const THREE = await import("three");
      if (disposed || motion.matches || ticket !== generation) return;
      let renderer: Three.WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
      } catch {
        return;
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
      renderer.setClearAlpha(0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.domElement.setAttribute("aria-hidden", "true");
      host.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 60);
      camera.position.set(3.1, 2.5, 12);
      camera.lookAt(0.3, 0, 0);
      const { assembly, innerOptics, paths, pathMaterials, packets, reviewPath, reviewPacket, palette } =
        buildLensModel(THREE, scene, getComputedStyle(host));

      // Studio reflections give the blackened metal and brass something to mirror.
      const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
      const pmrem = new THREE.PMREMGenerator(renderer);
      // 64 px is plenty for blurred reflections and a fraction of the default 256 px cost.
      const environment = pmrem.fromScene(new RoomEnvironment(), 0.04, 0.1, 100, { size: 64 }).texture;
      pmrem.dispose();
      scene.environment = environment;
      scene.environmentIntensity = 0.55;

      let frame = 0;
      let visible = true;
      let contextAlive = true;
      let elapsed = 0;
      let lastTime = 0;
      let scrollProgress = 0;
      const pointer = { x: 0, y: 0 };
      const selectedColor = palette.signal;
      const idleColor = palette.path;

      function render(time: number) {
        frame = 0;
        if (disposed || !visible || !contextAlive || document.hidden || motion.matches) return;
        elapsed += lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0;
        lastTime = time;
        assembly.rotation.y +=
          (-0.28 + pointer.x * 0.13 + scrollProgress * 0.32 - assembly.rotation.y) * 0.045;
        assembly.rotation.x += (0.12 + pointer.y * 0.075 - assembly.rotation.x) * 0.045;
        assembly.rotation.z = -0.16 + scrollProgress * 0.07;
        innerOptics.rotation.z = elapsed * 0.035;
        const active = channelOrder.indexOf(activeRef.current);
        pathMaterials.forEach((material, i) =>
          material.color.lerp(i === active ? selectedColor : idleColor, 0.08),
        );
        packets.forEach((packet) => {
          const t = (elapsed * 0.045 + packet.userData.offset + packet.userData.lane * 0.12) % 1;
          packet.position.copy(paths[packet.userData.lane].getPointAt(t));
          packet.scale.setScalar(packet.userData.lane === active ? 1.4 : 0.8);
        });
        reviewPacket.position.copy(reviewPath.getPointAt((elapsed * 0.11 + 0.4) % 1));
        renderer.render(scene, camera);
        frame = requestAnimationFrame(render);
      }
      function resume() {
        lastTime = 0;
        if (!frame && visible && contextAlive && !document.hidden && !motion.matches)
          frame = requestAnimationFrame(render);
      }
      function resize() {
        if (!host) return;
        const { width, height } = host.getBoundingClientRect();
        renderer.setSize(width, height);
        camera.aspect = width / Math.max(height, 1);
        camera.fov = width < 600 ? 42 : 32;
        camera.position.x = width < 600 ? 1.8 : 3.1;
        camera.lookAt(width < 600 ? 0.9 : 0.3, 0, 0);
        camera.updateProjectionMatrix();
        renderer.render(scene, camera);
      }
      function move(event: PointerEvent) {
        if (!finePointer.matches || !host) return;
        const rect = host.getBoundingClientRect();
        pointer.x = (event.clientX - rect.left) / rect.width - 0.5;
        pointer.y = (event.clientY - rect.top) / rect.height - 0.5;
      }
      function leave() {
        pointer.x = 0;
        pointer.y = 0;
      }
      function scroll() {
        const hero = host?.closest("section");
        if (hero)
          scrollProgress = Math.max(0, Math.min(1, -hero.getBoundingClientRect().top / hero.offsetHeight));
      }
      function visibility() {
        if (document.hidden && frame) {
          cancelAnimationFrame(frame);
          frame = 0;
        } else resume();
      }
      function contextLost(event: Event) {
        event.preventDefault();
        contextAlive = false;
        if (frame) cancelAnimationFrame(frame);
        frame = 0;
        setReady(false);
      }
      const observer = new IntersectionObserver(
        ([entry]) => {
          visible = entry.isIntersecting;
          if (!visible && frame) {
            cancelAnimationFrame(frame);
            frame = 0;
          } else resume();
        },
        { rootMargin: "80px" },
      );
      observer.observe(host);
      const sizeObserver = new ResizeObserver(resize);
      sizeObserver.observe(host);
      host.addEventListener("pointermove", move);
      host.addEventListener("pointerleave", leave);
      renderer.domElement.addEventListener("webglcontextlost", contextLost);
      document.addEventListener("visibilitychange", visibility);
      window.addEventListener("scroll", scroll, { passive: true });
      resize();
      setReady(true);
      resume();

      stopScene = () => {
        if (frame) cancelAnimationFrame(frame);
        observer.disconnect();
        sizeObserver.disconnect();
        host.removeEventListener("pointermove", move);
        host.removeEventListener("pointerleave", leave);
        renderer.domElement.removeEventListener("webglcontextlost", contextLost);
        document.removeEventListener("visibilitychange", visibility);
        window.removeEventListener("scroll", scroll);
        disposeScene(THREE, scene);
        environment.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        renderer.domElement.remove();
      };
    }

    function motionChanged() {
      generation++;
      stopScene?.();
      stopScene = undefined;
      setReady(false);
      if (!motion.matches) void createScene();
    }
    void createScene();
    motion.addEventListener("change", motionChanged);
    return () => {
      disposed = true;
      motion.removeEventListener("change", motionChanged);
      stopScene?.();
    };
  }, [animated]);

  return (
    <div
      className={`lens-visual${ready ? " lens-visual--ready" : ""}`}
      role="img"
      aria-label="An optical lens brings four payment streams into focus and routes suspicious activity for review."
    >
      <LensPoster />
      <div className="lens-canvas" ref={hostRef} />
    </div>
  );
}
