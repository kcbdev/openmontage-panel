"use client";

import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const STAGES = [
  "research",
  "proposal",
  "script",
  "storyboard",
  "scene_plan",
  "assets",
  "edit",
  "publish",
];

export function StageTracker({
  currentStage,
}: {
  currentStage: string | null;
}) {
  const idx = currentStage ? STAGES.indexOf(currentStage) : -1;

  return (
    <div className="flex items-center gap-0 w-full">
      {STAGES.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <div key={s} className="flex-1 flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium border-2 transition-colors",
                  done && "bg-blue-600 border-blue-600 text-white",
                  active &&
                    "border-blue-600 text-blue-600 bg-blue-50 animate-pulse",
                  !done && !active && "border-gray-200 text-gray-400 bg-white"
                )}
              >
                {done ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  <span>{i + 1}</span>
                )}
              </div>
              <span
                className={cn(
                  "text-[10px] leading-tight text-center hidden sm:block",
                  active && "text-blue-600 font-medium",
                  done && "text-gray-500",
                  !done && !active && "text-gray-400"
                )}
              >
                {s.replace("_", " ")}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div
                className={cn(
                  "h-0.5 flex-1 mx-1",
                  i < idx ? "bg-blue-600" : "bg-gray-200"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function LiveProgressView({
  currentStage,
}: {
  currentStage: string | null;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
      <p className="text-sm text-gray-600">
        {currentStage ? `Working on ${currentStage.replace("_", " ")}` : "Starting up"}
      </p>
      <p className="text-xs text-gray-400 mt-1">
        Checkpoints will appear here as each stage completes
      </p>
    </div>
  );
}
