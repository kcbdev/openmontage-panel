export function CostMeter({
  current,
  cap = 10,
}: {
  current: number;
  cap?: number;
}) {
  const pct = Math.min((current / cap) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>Cost</span>
        <span>
          ${current.toFixed(2)} / ${cap.toFixed(2)} cap
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct > 80 ? "bg-red-500" : pct > 50 ? "bg-yellow-500" : "bg-blue-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
