# Mission Control — User Journeys

Each journey maps to the panels from the architecture doc (Fleet View, Launch Console, Command Deck, Mission Archive, Ground Systems) and calls out which pain point from the product doc it's resolving.

---

## Journey 1 — First deploy (self-hosted setup)

**Who:** A freelancer or agency owner setting up their own instance for the first time.

1. Clicks the one-click Coolify deploy template (or runs the CLI installer) → stack provisions: `mission-control-web`, `mission-control-api`, `postgres`, `redis`, `minio`.
2. First-load wizard: create owner account, set instance name.
3. **Ground Systems → Provider Credentials**: paste API keys for the providers they already have (fal.ai, ElevenLabs, etc.) or skip entirely and rely on free-tier providers only. Test-connection button confirms each key works before saving.
4. **Ground Systems → Budget**: set an instance-wide default cap and mode (observe/warn/cap). Defaults to "warn" so nothing is blocked on day one.
5. Lands on an empty **Fleet View** with a single prompt: "Launch your first project."

*Resolves:* platform-risk anxiety (data never leaves their server), opaque pricing (cap is set before any spend happens, not discovered after).

---

## Journey 2 — First video, Guided mode

**Who:** A non-technical user, first project ever.

1. **Fleet View** (empty) → "New Launch" → **Launch Console**.
2. Three questions only: what's the video about (text brief, or paste a reference video URL), how long, cost dial (Free / Balanced / Premium).
3. System responds with: auto-picked pipeline (editable — "we think this is an Explainer video, change it?"), a cost estimate in real currency, and if a reference video was pasted, 2-3 concept variants to choose from.
4. User confirms → **Launch** → supervisor graph provisions the engine container → Fleet card flips to 🟢 nominal, "Research" stage.
5. A few minutes later, Fleet card flips to 🟡 awaiting decision. Push/in-app notification: "Script ready for your review."
6. User opens **Command Deck**: script renders as a screenplay page. Buttons: Approve / Request revision (with a text note) / Reject.
7. User approves → stage advances → same pattern repeats at scene-plan and asset gates, each shown as a storyboard contact sheet with per-scene thumbnails and cost.
8. Final gate: publish approval, showing the composed video inline, total cost vs. estimate.
9. User approves → **Mission Archive** now holds the finished project: download, or "Remix" to fork it.

*Resolves:* choice paralysis (3 inputs, not 20 parameters), redo-the-whole-video pain (each gate is scoped to what actually needs a decision), cost anxiety (estimate shown before commit, running total visible throughout).

---

## Journey 3 — Fixing one bad scene (the critical-path journey)

**Who:** Any user, mid-run, at the scene-plan or asset gate.

1. In **Command Deck**, the storyboard contact sheet shows 8 scene thumbnails. Scene 4 looks wrong — wrong mood, bad take.
2. User clicks scene 4 → inline options: Regenerate (optionally override the provider for just this scene) or Lock (keep as-is).
3. User locks scenes 1-3 and 5-8, regenerates scene 4 only.
4. Supervisor graph resumes the Driver with a scoped instruction — only unlocked scenes re-execute downstream.
5. New take for scene 4 appears in the same contact sheet within its normal generation time; the other 7 scenes are untouched, no cost re-incurred on them.
6. User approves the full storyboard → pipeline continues to edit/compose.

*Resolves:* the single most-cited industry pain point — one bad shot forcing a full, costly re-run.

---

## Journey 4 — Async, delayed approval

**Who:** A busy user who can't respond to a gate immediately.

1. Gate fires (e.g., asset approval) while the user is away. Fleet card sits at 🟡 for hours — this is normal, not a failure state.
2. Notification sent (email/push), but the run doesn't block anything else — other projects in the Fleet keep progressing independently.
3. Three hours later, user opens Mission Control from their phone. **Fleet View** immediately shows which of their 4 active projects need attention, sorted by wait time.
4. User taps into the waiting project, reviews on mobile (storyboard contact sheet is touch-friendly, thumbnails not a dense timeline), approves from the couch.
5. Run resumes automatically, no re-entry of context needed — the Command Deck shows exactly what it showed 3 hours ago.

*Resolves:* the false assumption that gates are blocking/synchronous like a chat reply; treats "waiting on you" as an ambient status, not an interruption.

---

## Journey 5 — Power user, Studio mode

**Who:** An experienced editor who knows exactly what they want.

1. **Launch Console** → toggles "Advanced."
2. Full parameter form: pipeline picked manually (Cinematic Montage), render runtime locked to Remotion, footage mode set to hybrid, per-capability providers manually pinned (Kling for video gen, ElevenLabs for narration, Suno for music), style playbook cloned from a built-in and tweaked, quality-gate strictness raised to max, budget cap overridden higher than the tenant default for this one project.
3. Launches with full manual control — same supervisor graph and Driver underneath, no different code path, just every field explicitly set instead of defaulted.
4. At each gate, this user tends to reject-and-revise more precisely (e.g., "scene 4, more contrast, less camera movement") rather than accepting first takes — the revision-notes field is doing real work for this persona.
5. On completion, saves the whole parameter set as a **Mission Profile** (template) named "Client X house style" for reuse across future projects.

*Resolves:* the bimodal control problem — this user never touches Guided mode again, but it's the same backend, so nothing was left on the table by keeping the product simple by default.

---

## Journey 6 — Team collaboration, separated roles

**Who:** An agency with an editor (drives projects) and an owner (approves spend/publish).

1. Owner invites the editor via **Ground Systems → Team**, assigns role "editor" (can launch and manage projects, cannot approve publish gates or change budget caps).
2. Editor launches a project in Studio mode, works through research/script/scene gates themselves.
3. At the **publish gate**, the system requires an "owner" role to approve (configurable per tenant) — the editor sees the gate as "waiting on owner approval," not as their own action item.
4. Owner gets notified, opens **Command Deck**, reviews the final composed video and total cost, approves.
5. Both editor and owner see the same Mission Archive entry afterward, with the decision log showing who approved what and when.

*Resolves:* need for spend/publish accountability separate from creative execution — a common real-world requirement not addressed by any single-user AI video tool in the competitive set.

---

## Journey 7 — Anomaly / failure recovery

**Who:** Any user, mid-run, when something breaks (provider API failure, container crash, stalled generation).

1. Fleet card flips to 🔴 anomaly instead of the normal 🟡/🟢 states.
2. **Command Deck** shows plainly what failed (e.g., "Video generation provider timed out on scene 6") and at which checkpoint — not a raw stack trace.
3. Options: Retry (same provider), Retry with different provider (system suggests the next-best-scored alternative), or Roll back to the last good checkpoint and resume manually.
4. User picks "retry with different provider" → supervisor graph resumes the Driver from the last good checkpoint with the override applied — no work prior to scene 6 is lost or re-run.
5. Decision log records the failure and the recovery action, visible later in Mission Archive for audit.

*Resolves:* trust — an opaque failure with no recovery path is worse than a slow one; this makes failure a normal, low-stakes branch of the journey rather than a dead end.

---

## Journey 8 — Remix from the library

**Who:** A returning user who wants "the same thing again, slightly different."

1. **Fleet View** → filters to "Archived" → finds last month's product-launch explainer.
2. Clicks **Remix** → **Launch Console** opens pre-filled with that project's full parameter set and style, brief field blanked for a new topic.
3. Optionally, changes just the cost dial (e.g., "same as before, but Premium instead of Free") to compare quality without re-deciding everything else.
4. Launches — new project in the Fleet, linked in Mission Archive back to its parent as "remixed from."

*Resolves:* turns the library from a flat archive into a genuine reuse loop — the mechanism by which a house style accumulates over time without manual re-configuration each time.

---

## Journey map summary

| Journey | Primary panel | Pain point resolved |
|---|---|---|
| 1. First deploy | Ground Systems | Platform risk, pricing opacity |
| 2. First video (Guided) | Launch Console → Command Deck | Choice paralysis |
| 3. Fix one bad scene | Command Deck | Whole-pipeline redo cost |
| 4. Async approval | Fleet View (mobile) | False "blocking chat" mental model |
| 5. Power user (Studio) | Launch Console (Advanced) | Bimodal control problem |
| 6. Team roles | Ground Systems → Command Deck | No accountability separation elsewhere in market |
| 7. Anomaly recovery | Command Deck | Opaque failure, no recovery path |
| 8. Remix | Fleet View → Launch Console | Flat, non-reusable libraries elsewhere |
