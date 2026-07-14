"use client";

import { useRequireAuth } from "@/lib/auth-context";
import { CredentialList } from "@/components/settings/CredentialList";
import { BudgetConsole } from "@/components/settings/BudgetConsole";
import { MemberList } from "@/components/settings/MemberList";
import { ProfileList } from "@/components/settings/ProfileList";

export default function SettingsPage() {
  useRequireAuth();

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      <BudgetConsole />
      <CredentialList />
      <MemberList />
      <ProfileList />
    </div>
  );
}
