"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const TIERS = [
  {
    id: "free",
    label: "Free",
    description: "Stock footage + local generation only",
    color: "bg-gray-100 text-gray-700 border-gray-200",
    activeColor: "bg-blue-100 text-blue-700 border-blue-500",
  },
  {
    id: "balanced",
    label: "Balanced",
    description: "Best quality for the price",
    color: "bg-gray-100 text-gray-700 border-gray-200",
    activeColor: "bg-blue-100 text-blue-700 border-blue-500",
  },
  {
    id: "premium",
    label: "Premium",
    description: "Top models, highest quality",
    color: "bg-gray-100 text-gray-700 border-gray-200",
    activeColor: "bg-blue-100 text-blue-700 border-blue-500",
  },
] as const;

export function CostDial({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Budget
        </label>
        <div className="flex gap-3">
          {TIERS.map((tier) => (
            <button
              key={tier.id}
              onClick={() => onChange(tier.id)}
              className={`flex-1 border rounded-lg p-3 text-center text-sm transition-colors ${
                value === tier.id ? tier.activeColor : tier.color
              }`}
            >
              <div className="font-medium">{tier.label}</div>
              <div className="text-xs mt-1 opacity-70">{tier.description}</div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
