"use client";

import { useEffect, useRef, useState } from "react";
import type * as Three from "three";
import type { ChannelKey } from "./channels";
import { LensPoster } from "./LensPoster";

const channelOrder: ChannelKey[] = ["upi", "netbanking", "card", "atm"];

export default function LensScene({ channel, animated = true }: { channel: ChannelKey; animated?: boolean }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef(channel);
  const [ready, setReady] = useState(false);
  useEffect(() => { activeRef.current = channel; }, [channel]);

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
      if (motion.matches || disposed || !host) return;
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
      const assembly = new THREE.Group();
      assembly.position.set(1.35, 0.15, 0);
      assembly.rotation.set(0.12, -0.28, -0.16);
      scene.add(assembly);

      // Palette from tokens.css (--lens-*), so the scene follows the design system.
      const css = getComputedStyle(host);
      const tone = (name: string) => new THREE.Color(css.getPropertyValue(name).trim());
      const palette = {
        glass: tone("--lens-glass"), rim: tone("--lens-rim"), metal: tone("--lens-metal"),
        path: tone("--lens-path"), signal: tone("--lens-signal"), risk: tone("--lens-risk"), light: tone("--on-dark"),
      };

      // Studio reflections give the blackened metal and brass something to mirror.
      const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
      const pmrem = new THREE.PMREMGenerator(renderer);
      const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      pmrem.dispose();
      scene.environment = environment;
      scene.environmentIntensity = 0.55;

      const steel = new THREE.MeshStandardMaterial({ color: palette.metal, metalness: 0.9, roughness: 0.32 });
      const polished = new THREE.MeshStandardMaterial({ color: palette.light, metalness: 0.75, roughness: 0.22 });
      const brass = new THREE.MeshStandardMaterial({ color: palette.rim, metalness: 0.95, roughness: 0.26 });
      const blackened = new THREE.MeshStandardMaterial({ color: palette.glass, metalness: 0.85, roughness: 0.4 });
      const glass = new THREE.MeshPhysicalMaterial({
        color: palette.glass, metalness: 0, roughness: 0.08, transparent: true, opacity: 0.55,
        side: THREE.DoubleSide, depthWrite: false, clearcoat: 1, clearcoatRoughness: 0.05,
      });

      function ring(radius: number, tube: number, z: number, material: Three.Material) {
        const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 12, 112), material);
        mesh.position.z = z;
        mesh.castShadow = true;
        assembly.add(mesh);
        return mesh;
      }
      ring(1.91, 0.075, -0.54, steel);
      ring(1.92, 0.045, -0.34, polished);
      ring(1.88, 0.105, -0.1, steel);
      ring(1.86, 0.115, 0.19, blackened);
      ring(1.86, 0.07, 0.32, brass);
      ring(1.73, 0.018, 0.34, polished);
      ring(1.55, 0.012, 0.35, brass);
      ring(1.2, 0.008, 0.36, brass);
      ring(0.65, 0.012, 0.37, polished);

      const lens = new THREE.Mesh(new THREE.SphereGeometry(1.71, 48, 32), glass);
      lens.scale.z = 0.105;
      lens.position.z = 0.21;
      assembly.add(lens);

      const ticks = new THREE.InstancedMesh(new THREE.BoxGeometry(0.015, 0.075, 0.017), polished, 96);
      const matrix = new THREE.Object3D();
      for (let i = 0; i < 96; i++) {
        const a = i / 96 * Math.PI * 2;
        matrix.position.set(Math.sin(a) * 1.86, Math.cos(a) * 1.86, 0.405);
        matrix.rotation.z = -a;
        matrix.scale.set(1, i % 8 === 0 ? 1.8 : 1, 1);
        matrix.updateMatrix();
        ticks.setMatrixAt(i, matrix.matrix);
      }
      assembly.add(ticks);

      const bolts = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.043, 0.043, 0.72, 8), steel, 8);
      for (let i = 0; i < 8; i++) {
        const a = i / 8 * Math.PI * 2;
        matrix.position.set(Math.sin(a) * 1.83, Math.cos(a) * 1.83, -0.1);
        matrix.rotation.set(Math.PI / 2, 0, 0);
        matrix.scale.set(1, 1, 1);
        matrix.updateMatrix();
        bolts.setMatrixAt(i, matrix.matrix);
      }
      assembly.add(bolts);

      // Thin concentric optics keep the inner assembly readable through the glass.
      const innerOptics = new THREE.Group();
      for (let i = 0; i < 6; i++) {
        const arc = new THREE.Mesh(new THREE.TorusGeometry(0.52 + i * 0.055, 0.008, 4, 56, Math.PI * 1.42), i % 2 ? steel : brass);
        arc.rotation.z = i * 0.72;
        arc.position.z = -0.05 + i * 0.015;
        innerOptics.add(arc);
      }
      assembly.add(innerOptics);

      const paths: Three.CatmullRomCurve3[] = [];
      const pathMaterials: Three.MeshStandardMaterial[] = [];
      const packets: Three.Mesh[] = [];
      for (let lane = 0; lane < 4; lane++) {
        const y = (lane - 1.5) * 0.43;
        const path = new THREE.CatmullRomCurve3([
          new THREE.Vector3(-7.3, y - 0.25, -0.6),
          new THREE.Vector3(-4.3, y - 0.55, -0.8),
          new THREE.Vector3(-1.7, y * 0.7 - 0.2, -0.7),
          new THREE.Vector3(1.35, y * 0.24 + 0.15, 0.02),
          new THREE.Vector3(3.8, y * 0.9 + 0.15, 0.1),
          new THREE.Vector3(6.8, y + 0.45, 0),
        ]);
        paths.push(path);
        const material = new THREE.MeshStandardMaterial({ color: lane === 0 ? palette.signal : palette.path, roughness: 0.4, metalness: 0.4 });
        pathMaterials.push(material);
        scene.add(new THREE.Mesh(new THREE.TubeGeometry(path, 84, 0.012, 5, false), material));
        for (let p = 0; p < 3; p++) {
          const packet = new THREE.Mesh(new THREE.SphereGeometry(0.047, 10, 8), material);
          packet.userData = { lane, offset: p / 3 };
          packets.push(packet);
          scene.add(packet);
        }
      }
      const reviewPath = new THREE.CatmullRomCurve3([
        new THREE.Vector3(1.35, 0.15, 0.08),
        new THREE.Vector3(3.1, 0.4, 0.2),
        new THREE.Vector3(3.65, 1.8, 0),
        new THREE.Vector3(5.75, 2, -0.4),
      ]);
      const red = new THREE.MeshStandardMaterial({ color: palette.risk, emissive: palette.risk, emissiveIntensity: 0.35, roughness: 0.45 });
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(reviewPath, 48, 0.016, 6, false), red));
      const reviewPacket = new THREE.Mesh(new THREE.SphereGeometry(0.065, 16, 12), red);
      scene.add(reviewPacket);

      const shadow = new THREE.ShadowMaterial({ color: tone("--dark-deep"), opacity: 0.55 });
      const ground = new THREE.Mesh(new THREE.PlaneGeometry(24, 16), shadow);
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -2.12;
      ground.receiveShadow = true;
      scene.add(ground);
      // Warm key from the upper left, a brass rim from behind, a low neutral fill.
      scene.add(new THREE.HemisphereLight(palette.light, tone("--dark-deep"), 0.8));
      const key = new THREE.DirectionalLight(palette.light, 4.2);
      key.position.set(-3, 7, 6);
      key.castShadow = true;
      key.shadow.mapSize.set(1024, 1024);
      key.shadow.camera.left = -8;
      key.shadow.camera.right = 8;
      key.shadow.camera.top = 6;
      key.shadow.camera.bottom = -6;
      key.shadow.normalBias = 0.025;
      key.shadow.radius = 6;
      scene.add(key);
      const rim = new THREE.DirectionalLight(palette.rim, 5);
      rim.position.set(5, 2, -4);
      scene.add(rim);

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
        assembly.rotation.y += (-0.28 + pointer.x * 0.13 + scrollProgress * 0.32 - assembly.rotation.y) * 0.045;
        assembly.rotation.x += (0.12 + pointer.y * 0.075 - assembly.rotation.x) * 0.045;
        assembly.rotation.z = -0.16 + scrollProgress * 0.07;
        innerOptics.rotation.z = elapsed * 0.035;
        const active = channelOrder.indexOf(activeRef.current);
        pathMaterials.forEach((material, i) => material.color.lerp(i === active ? selectedColor : idleColor, 0.08));
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
        if (!frame && visible && contextAlive && !document.hidden && !motion.matches) frame = requestAnimationFrame(render);
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
      function leave() { pointer.x = 0; pointer.y = 0; }
      function scroll() {
        const hero = host?.closest("section");
        if (hero) scrollProgress = Math.max(0, Math.min(1, -hero.getBoundingClientRect().top / hero.offsetHeight));
      }
      function visibility() {
        if (document.hidden && frame) { cancelAnimationFrame(frame); frame = 0; }
        else resume();
      }
      function contextLost(event: Event) {
        event.preventDefault();
        contextAlive = false;
        if (frame) cancelAnimationFrame(frame);
        frame = 0;
        setReady(false);
      }
      const observer = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (!visible && frame) { cancelAnimationFrame(frame); frame = 0; }
        else resume();
      }, { rootMargin: "80px" });
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
        const geometries = new Set<Three.BufferGeometry>();
        const materials = new Set<Three.Material>();
        scene.traverse((object) => {
          if (object instanceof THREE.Mesh) {
            geometries.add(object.geometry);
            const meshMaterials = Array.isArray(object.material) ? object.material : [object.material];
            meshMaterials.forEach((material) => materials.add(material));
          }
        });
        geometries.forEach((geometry) => geometry.dispose());
        materials.forEach((material) => material.dispose());
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

  return <div className={`lens-visual${ready ? " lens-visual--ready" : ""}`} role="img" aria-label="An optical lens brings four payment streams into focus and routes suspicious activity for review."><LensPoster /><div className="lens-canvas" ref={hostRef} /></div>;
}
