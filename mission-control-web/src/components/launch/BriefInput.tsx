"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

export function BriefInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          What&apos;s the video about?
        </label>
        <Textarea
          placeholder="Describe your video in a sentence or two..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
        />
      </CardContent>
    </Card>
  );
}
