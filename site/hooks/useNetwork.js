import { useEffect, useState } from "react";
import { fetchData, validNodes, validStats } from "../data.js";

const initial = (file) => ({ data: file === "nodes.json" ? [] : null, source: "", status: "loading", error: false });

export default function useNetwork() {
  const [stats, setStats] = useState(() => initial("stats.json"));
  const [nodes, setNodes] = useState(() => initial("nodes.json"));
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setStats((current) => ({ ...current, status: "loading", error: false }));
    setNodes((current) => ({ ...current, status: "loading", error: false }));
    const load = (file, validate, update) => {
      fetchData(file, validate, controller.signal).then(({ data, source }) => {
        if (!controller.signal.aborted) update({ data, source, status: "ready", error: false });
      }).catch(() => {
        if (!controller.signal.aborted) update((current) => ({ ...current, status: "error", error: true }));
      });
    };
    load("stats.json", validStats, setStats);
    load("nodes.json", validNodes, setNodes);
    return () => controller.abort();
  }, [revision]);

  return {
    stats, nodes, now,
    retry: () => setRevision((value) => value + 1),
    consistent: Boolean(stats.source && nodes.source && stats.source === nodes.source),
  };
}
