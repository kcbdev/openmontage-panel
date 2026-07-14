"use client";

import useSWR from "swr";
import { apiClient } from "@/lib/api-client";

const CAPABILITY_MAP: Record<string, string> = {
  video_gen: "video_generation",
  image_gen: "image_generation",
  tts: "tts",
  music: "music_generation",
  audio: "audio_processing",
  avatar: "avatar",
  subtitle: "subtitle",
  enhancement: "enhancement",
  graphics: "graphics",
};

export function ProviderSelect({
  label,
  capability,
  value,
  onChange,
}: {
  label: string;
  capability: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { data: menu } = useSWR(
    "providerMenu",
    () => apiClient.getProviderMenu() as Promise<Record<string, { available: { name: string; provider: string }[] }>>,
  );

  const categoryKey = CAPABILITY_MAP[capability] || capability;
  const providers = menu?.[categoryKey]?.available ?? [];

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="">auto (let the engine pick)</option>
        {providers.map((p) => (
          <option key={p.name} value={p.name}>
            {p.provider} — {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}
