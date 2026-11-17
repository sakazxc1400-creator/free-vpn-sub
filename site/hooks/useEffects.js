import { useEffect, useRef, useState } from "react";

export default function useGlassPointer(ref) {
  useEffect(() => {
    const element = ref.current;
    const fine = window.matchMedia("(pointer: fine)");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!element || !fine.matches || reduced.matches || !("IntersectionObserver" in window)) return undefined;
    let frame = 0;
    let visible = true;
    const move = (event) => {
      if (!visible || frame) return;
      frame = requestAnimationFrame(() => {
        const rect = element.getBoundingClientRect();
        element.style.setProperty("--pointer-x", `${event.clientX - rect.left}px`);
        element.style.setProperty("--pointer-y", `${event.clientY - rect.top}px`);
        frame = 0;
      });
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    observer.observe(element);
    element.addEventListener("pointermove", move, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      element.removeEventListener("pointermove", move);
    };
  }, [ref]);
}

export function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(typeof target === "number" ? target : null);
  const from = useRef(0);
  useEffect(() => {
    if (typeof target !== "number" || !Number.isFinite(target)) {
      from.current = 0;
      setValue(null);
      return undefined;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      from.current = target;
      setValue(target);
      return undefined;
    }
    const start = performance.now();
    const origin = from.current;
    let frame = 0;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setValue(Math.round(origin + (target - origin) * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); from.current = target; };
  }, [target, duration]);
  return value;
}

export function useParallax(ref, strength = 10) {
  useEffect(() => {
    const element = ref.current;
    if (!element || !window.matchMedia("(pointer: fine)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
    let frame = 0;
    const move = (event) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        const rect = element.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - .5;
        const y = (event.clientY - rect.top) / rect.height - .5;
        element.style.setProperty("--parallax-x", `${(-x * strength).toFixed(2)}px`);
        element.style.setProperty("--parallax-y", `${(-y * strength).toFixed(2)}px`);
        frame = 0;
      });
    };
    const leave = () => {
      element.style.setProperty("--parallax-x", "0px");
      element.style.setProperty("--parallax-y", "0px");
    };
    element.addEventListener("pointermove", move, { passive: true });
    element.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerleave", leave);
    };
  }, [ref, strength]);
}

export function useReveal(ref) {
  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const items = root.querySelectorAll("[data-reveal]");
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
      items.forEach((item) => { item.dataset.visible = "true"; });
      return undefined;
    }
    try {
      const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.dataset.visible = "true";
            observer.unobserve(entry.target);
          }
        }
      }, { rootMargin: "0px 0px -8%", threshold: 0.05 });
      items.forEach((item) => observer.observe(item));
      return () => observer.disconnect();
    } catch {
      items.forEach((item) => { item.dataset.visible = "true"; });
      return undefined;
    }
  }, [ref]);
}
