import type { ApprovalGate } from "@/lib/types";
import { FileText, Layout, Image, Video } from "lucide-react";

export function ProposalView({ gate }: { gate: ApprovalGate }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileText className="w-5 h-5 text-gray-500" />
        <h3 className="text-lg font-medium">Proposal</h3>
      </div>
      <p className="text-sm text-gray-600">
        {gate.payload?.summary
          ? String(gate.payload.summary)
          : "Awaiting proposal content..."}
      </p>
    </div>
  );
}

export function ScreenplayView({ gate }: { gate: ApprovalGate }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileText className="w-5 h-5 text-gray-500" />
        <h3 className="text-lg font-medium">Script</h3>
      </div>
      <p className="text-sm text-gray-600">
        {gate.payload?.summary
          ? String(gate.payload.summary)
          : "Awaiting script content..."}
      </p>
    </div>
  );
}

export function StoryboardGrid({ gate }: { gate: ApprovalGate }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Layout className="w-5 h-5 text-gray-500" />
        <h3 className="text-lg font-medium">Storyboard / Scene Plan</h3>
      </div>
      <p className="text-sm text-gray-600">
        {gate.payload?.summary
          ? String(gate.payload.summary)
          : "Awaiting storyboard content..."}
      </p>
    </div>
  );
}

export function PublishPreview({ gate }: { gate: ApprovalGate }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Video className="w-5 h-5 text-gray-500" />
        <h3 className="text-lg font-medium">Final Render</h3>
      </div>
      <p className="text-sm text-gray-600">
        {gate.payload?.summary
          ? String(gate.payload.summary)
          : "Awaiting final render..."}
      </p>
      <div className="border-2 border-dashed border-gray-200 rounded-lg aspect-video flex items-center justify-center text-gray-400 text-sm">
        Video preview will appear when AI generation is enabled
      </div>
    </div>
  );
}
