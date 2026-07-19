import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

const scrollPositions = new Map<string, number>();

export function useScrollRestore(key?: string) {
  const location = useLocation();
  const restoreKey = key ?? location.key;
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = scrollPositions.get(restoreKey);
    if (saved != null && containerRef.current) {
      containerRef.current.scrollTop = saved;
    }
  }, [restoreKey]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      scrollPositions.set(restoreKey, container.scrollTop);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [restoreKey]);

  const saveScroll = () => {
    if (containerRef.current) {
      scrollPositions.set(restoreKey, containerRef.current.scrollTop);
    }
  };

  return { containerRef, saveScroll };
}
