# Phase 0.1 — AGPL License Review Memo

**License:** GNU Affero General Public License v3.0

## Architecture check

Mission Control's design was evaluated against AGPL §13 ("Remote Network Interaction; Use with the General Public License") and the FSF's guidance on "aggregate" vs. "modified" works.

### Finding: Mission Control is an aggregate, not a derivative work

- **No engine source is modified.** Mission Control builds the engine container from the exact upstream commit, copies it unmodified into the image, and invokes it via its standard ENTRYPOINT. No `#include`, no forked fork, no monkey-patch.

- **No engine source is linked.** The Driver calls the engine via filesystem I/O (checkpoints inbound, `pending_decision.json` outbound) and HTTP (Backlot API). This is inter-process communication, not linking. The engine runs as a separate process inside its own container.

- **The UI, API, and Postgres schema are genuinely new code.** They bear no structural similarity to any OpenMontage file. The supervisor graph is a simple container-lifecycle state machine — OpenMontage has nothing like it.

### Residual risk

- **AGPL §13 (the "ASP loophole" clause):** If Mission Control modified the engine, then *users interacting with Mission Control over a network* would be entitled to receive the engine's full source code. Because Mission Control does not modify or link to the engine, §13 is not triggered. The engine is a separate program that happens to run in the same Docker compose stack.

- **The entrypoint.sh injection is the boundary.** `entrypoint.sh` sets `FORCED_PROVIDERS` and `MODEL_ROUTING` env vars before exec'ing the engine's own code. This is configuration injection, not code modification — the engine's own code knows how to read these env vars (they correspond to existing OpenMontage configuration mechanisms).

- **If the AGPL is still concerning, ask a lawyer.** The FSF's own FAQ on AGPL aggregates supports this reading. The cleanest hedge: keep the engine image build separate (it is — `mission-control/engine/Dockerfile` builds from the upstream repo, not a forked source tree).

## Recommendation

Proceed. Phase 7 (license memo gating the hosted/paid offering) will revisit distribution terms, but Phase 0-6 engineering is structurally clean.
