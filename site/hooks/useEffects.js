import { useEffect } from "react";

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
