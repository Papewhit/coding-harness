# Coda v3 Structured Context Asset Contract

## Purpose

This is the Coda namespace successor to the historical v3 context-asset freeze. It replaces the single-prompt-string assumption with four explicit request surfaces: `system_text`, `messages`, `tools`, and `continuation`. The machine-readable source is `benchmarks/v3/context-assets/assets.json`; this document explains its normative meaning and records which behaviors are merely observed in the current Runtime.

EVAL-030 defines an evaluation target. It does not change `ContextManager`, request composition, compaction, or native Runtime wiring.

## Surface boundaries

| Surface | Carries | Must not carry |
| --- | --- | --- |
| `system_text` | Stable instructions and activated control assets | Native tool schemas or signatures copied from `tools`; opaque provider state |
| `messages` | Current request, public turn history, native call/results, worker notifications, compact summaries, pointer carriers | Private reasoning/thinking or opaque continuation bodies |
| `tools` | Provider-neutral native tool definitions only | Prompt prose, memory, plan, or duplicated system-text signatures |
| `continuation` | JSON-safe opaque provider continuation needed for native resume | Public prompt assets or content exposed in reports |

The active native tool catalog belongs only to `tools`. A schema, parameter signature, or equivalent definition appearing in `system_text` is a contract failure, not an optimization. Evidence may record the catalog hash and count without copying the catalog.

The current user request is a protected message: it is verbatim, non-compactable, and never-drop. If the request alone exceeds a provider limit, composition must fail explicitly rather than silently crop it.

An unfinished native turn is also non-compactable. Until every provider call ID has exactly one terminal result, public call/result messages and any required opaque continuation must remain pairable. Compaction may operate only across a completed boundary.

## Asset policies

| Asset | Producer | Activation and lifetime | Primary target | Priority and floor | Drop and duplication policy |
| --- | --- | --- | --- | --- | --- |
| Skills | Skill registry and selected skill renderer | Catalog while enabled; body per activation; workspace catalog plus turn activation | `system_text` | Medium; preserve catalog identity and activation metadata | Drop inactive bodies before catalog; one catalog entry and one activated body |
| Todo | `TodoLedger` | Non-empty ledger or mode guidance; session until terminal/removal | `system_text` | High; preserve every non-terminal item's id, status, priority, and content | Terminal items yield before active items; current ledger has one authority |
| Plan | `PlanModeManager` and active plan artifact | Plan mode only | `system_text` | Critical; preserve mode, pointer, write constraint, completion gate, and progress pointer | Never drop while active; carry policy plus pointer, not duplicate the full plan |
| Checkpoint | `RuntimeCheckpointsMixin` | Compatible checkpoint during resume; until superseded, invalid, or complete | `system_text` | High; preserve id, goal, blocker, next step, freshness, and runtime identity | Fresh resume core cannot silently disappear; stale content becomes explicit stale status plus pointer |
| Worker | `WorkerManager` and notification renderer | Worker transition or undrained notification; session state plus drain lifetime | `messages` | High; preserve worker id, state, action, result summary/pointer, and drain state | Undrained transitions never drop; large results become pointers, not copies |
| Durable | Durable memory index and retrieval | Memory enabled and policy/note selected; workspace lifetime | `system_text` | Medium; preserve policy and selected source identity/freshness/pointer | Unselected bodies yield first; the index remains pointer-only and selected bodies have one carrier |
| Compact | `CompactManager` | After completed old turns are summarized; until replaced | `messages` | High; preserve trigger, covered boundary, progress/critical context, and source hash | Latest summary needs a replacement before removal; source turns are replaced, not duplicated |
| Pointer | All externalizing producers | Content is externalized, clipped, stale, large, or deliberately referenced | Artifact pointer metadata on a message or system carrier | High; preserve kind, target, hash, freshness, producer, and resolvability | A sole valid reference never drops; referenced bodies are not copied across surfaces |

`continuation` is intentionally not the primary target of any of the eight domain assets. It is reserved for provider-native continuation. Putting a plan, memory note, worker result, or compact summary into opaque continuation would make the public request and evidence irreconstructible.

## Priority, floors, and drop decisions

Priority orders conflict resolution: `critical`, `high`, `medium`, then `low`. A floor describes semantic content, not a character quota. Budget reduction must first remove inactive or replaceable material, then summarize or externalize according to the asset's policy. Every clip, summary, pointer substitution, replacement, or drop is an explicit `drop_action` in evidence.

The contract distinguishes three policy levels:

- `guaranteed` is normative and directly fail-able by evaluation.
- `observed` describes the current implementation and is not promoted to a promise.
- `target` is required of the eventual structured Runtime but is not implemented by EVAL-030.

This prevents current character-budget behavior from accidentally becoming the v3 contract.

## Observed versus guaranteed

| Concern | Current observation | Contract guarantee or target |
| --- | --- | --- |
| Request shape | `ContextManager.build()` returns one assembled string and metadata | Requests are attributable across four explicit surfaces |
| Current request | Appended last and excluded from section-budget clipping | Guaranteed verbatim, never-drop, non-compactable `messages` content |
| Tools | Current context accounting includes rendered tool text; native schema export now exists | Guaranteed tool definitions only in `tools`, with zero system-text definition matches |
| Skills | Rendered into a skills section and tail-clipped to a character floor | Target separates catalog floor from activated body and records every reduction |
| Todo | Appended inside the generic memory section | Target gives active items their own high-priority floor |
| Plan | Plan-mode policy is refreshed into the prefix | Guaranteed active control core; target exposes separate asset evidence |
| Checkpoint | Rendered checkpoint text is appended inside memory | Target preserves resume core or emits explicit stale replacement |
| Worker | Completion notification is drained into a coordinator turn | Target represents each transition as an attributable message with result hash/pointer |
| Durable | Policy is in memory; selected durable notes are mixed with relevant memory | Target records selected identities, hashes, freshness, and single-carrier routing |
| Compact | Older completed turn groups become a `compact_summary`; recent turns remain | Target preserves covered boundaries and forbids compaction across an unfinished native turn |
| Pointer | Paths and IDs occur in several textual fragments | Guaranteed resolvable pointer metadata when a pointer is the sole carrier |
| Continuation | Native contracts define JSON-safe opaque continuation, but Context Runtime is not wired | Guaranteed privacy boundary and hash-only public evidence; no domain asset bodies |

## Evidence and evaluation

Each composed request records the contract version, request ID, per-surface hashes, activated asset IDs, asset records, duplication findings, and native-turn status. Every activated asset record includes producer, surface, activation, priority, floor result, raw/rendered size, content hash, drop action, and asset metadata.

Provider token counts are preferred. If unavailable, evaluators use UTF-8 bytes and record the method. Public artifacts never contain opaque reasoning/thinking. For private continuation they record only type, count, hash, and token usage.

Normal-budget fixtures should use a unique sentinel for each asset and assert its target surface or pointer metadata. Pressure fixtures should assert semantic floors and explicit drop actions rather than depend on today's section character constants. Native-turn fixtures must prove that compaction neither orphans a result nor removes required continuation before the terminal result boundary.

## Frozen inputs

This contract is frozen against these Coda inputs:

- artifact contract: `a4882493c07ae7582c8286882d22f5da495482e34070f60bae8fa1daef258dea`
- native contract: `cf961b5f72b06a024abadaff48dbccb4520fb93a9a1665fc66742652db5a79eb`
- tool schema catalog: `994a17e9f5c37d275f303176a67bf776324f972914d2b451df785b8205d7818f`
- context assets: `35daef1235d27af82bd7343d859eb0cc185ae01225c64e675109f6764ef25b01`
- C01-C08 fragment: `d9e65ee5570ba862af8e8cd6ef5d5bca15b27f9bb1bf3a8e0a8219b85e93ff5e`
- C09-C15 fragment: `ba0141a548a70a1aedd292a70cf7960bf190144bf1985c540bc27ec60a11ef03`
- assembled cases Git blob: OID `c3ca89d08163111f7612557a85e7ac477388378a`, SHA-256 `6feadd16451408ff77596e8cabf357b2fc20eda8ea0c0934f5db35373346638d`, 59,801 bytes

Changing an input requires a new contract version and a deliberate freeze proposal; downstream fixtures must not silently reinterpret this version.

The canonical binding is `benchmarks/v3/context-assets/cases-v3.binding.json`. Its provenance points to `eval-v2/p5-integrated:benchmarks/v3/context-assets/cases-v2.binding.json` at Git blob `3426371758b7bb9569680e271d3d782a486d2bd1`. This records the immutable source of the successor without copying the historical schema into the current contract and without claiming a new evaluation.
