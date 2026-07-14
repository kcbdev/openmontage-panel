"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";

export function DurationSlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Duration: {value}s
        </label>
        <Slider
          min={15}
          max={120}
          step={5}
          value={[value]}
          onValueChange={(v) => {
            const val = Array.isArray(v) ? v[0] : v;
            onChange(val ?? value);
          }}
        />
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>15s</span>
          <span>120s</span>
        </div>
      </CardContent>
    </Card>
  );
}
