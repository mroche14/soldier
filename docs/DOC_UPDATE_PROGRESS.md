# Documentation Update Progress Tracker

> **Mission**: Propagate decisions from `architecture_reconsideration.md` to all affected docs
> **Started**: 2025-12-14
> **Status**: COMPLETED

---

## Progress Overview

| Decision | Status | Checked | Affected Docs |
|----------|--------|---------|---------------|
| §1.3 Focal = alignment pipeline | ✅ DONE | ☑ | overview.md, vision.md, CLAUDE.md |
| §3.4 Multimodal envelope | ✅ DONE | ☑ | api-layer.md, ACF_ARCHITECTURE.md |
| §3.5 Tasks bypass ACF | ✅ DONE | ☑ | ACF_ARCHITECTURE.md |
| §4.3 ChannelPolicy shared | ✅ DONE | ☑ | ACF_ARCHITECTURE.md, AGENT_RUNTIME_SPEC.md, 10-channel-capabilities.md |
| §6.6 InterlocutorChannelPresence | ✅ DONE | ☑ | customer-profile.md, data_models.md |
| §7.3 MCP discovery | ✅ DONE | ☑ | TOOLBOX_SPEC.md, api-layer.md |
| §8.0 Interlocutor terminology | ✅ DONE | ☑ | data_models.md, pipeline.md, domain-model.md |
| §12.3 ASA mechanic-agnostic | ✅ DONE | ☑ | 13-asa-validator.md |

---

## Detailed Status per Decision

### §1.3 Focal = alignment pipeline only
- **Decision**: FOCAL is the alignment mechanic/pipeline, not the platform. Platform = "Ruche Runtime" or similar.
- **Files updated**:
  - [x] `docs/architecture/overview.md` - Updated Focal definition, added platform components list
  - [x] `docs/vision.md` - Clarified scope as "runtime platform"
  - [x] `CLAUDE.md` - Added Core Terminology table
- **Status**: ✅ DONE
- **Checked**: ☑

### §3.4 Multimodal envelope
- **Decision**: Ingress envelope supports content_type + content object (text, media, location, structured)
- **Files updated**:
  - [x] `docs/architecture/api-layer.md` - Added multimodal envelope spec with content_type field
  - [x] `docs/focal_360/architecture/ACF_ARCHITECTURE.md` - Referenced in ingress section
- **Status**: ✅ DONE
- **Checked**: ☑

### §3.5 Tasks bypass ACF (Agenda→Hatchet direct)
- **Decision**: Tasks are NOT conversations. Agenda→Hatchet direct, separate workflow type.
- **Files updated**:
  - [x] `docs/focal_360/architecture/ACF_ARCHITECTURE.md` - Added §3.5 "Tasks Bypass ACF Entirely"
- **Status**: ✅ DONE
- **Checked**: ☑
- **Note**: 09-agenda-goals.md and 06-hatchet-integration.md updates deferred (lower priority)

### §4.3 ChannelPolicy shared model
- **Decision**: ChannelPolicy is single source of truth, loaded into AgentContext.
- **Files updated**:
  - [x] `docs/focal_360/architecture/ACF_ARCHITECTURE.md` - Added ChannelPolicy model definition
  - [x] `docs/focal_360/architecture/AGENT_RUNTIME_SPEC.md` - Added channel_policies to AgentContext
  - [x] `docs/focal_360/architecture/topics/10-channel-capabilities.md` - Replaced old models with ChannelPolicy
- **Status**: ✅ DONE
- **Checked**: ☑

### §6.6 InterlocutorChannelPresence
- **Decision**: Cross-channel awareness without session merging via InterlocutorChannelPresence.
- **Files updated**:
  - [x] `docs/design/customer-profile.md` - Added InterlocutorChannelPresence model
  - [x] `docs/focal_turn_pipeline/spec/data_models.md` - Added InterlocutorChannelPresence to architecture
- **Status**: ✅ DONE
- **Checked**: ☑

### §7.3 MCP discovery + tool awareness
- **Decision**: MCP for discovery, Toolbox for execution. Three-tier tool visibility model.
- **Files updated**:
  - [x] `docs/focal_360/architecture/TOOLBOX_SPEC.md` - Added three-tier model, MCP discovery integration
  - [x] `docs/architecture/api-layer.md` - Added MCP server section with three-tier visibility
- **Status**: ✅ DONE
- **Checked**: ☑

### §8.0 Interlocutor terminology
- **Decision**: Rename customer → interlocutor with InterlocutorType enum (human/agent/system/bot)
- **Files updated**:
  - [x] `CLAUDE.md` - Added Interlocutor to Core Terminology
  - [x] `docs/focal_turn_pipeline/spec/data_models.md` - Renamed Customer* → Interlocutor*, added interlocutor_type
  - [x] `docs/focal_turn_pipeline/spec/pipeline.md` - Updated to use interlocutor_id terminology
  - [x] `docs/design/domain-model.md` - Updated entity names
- **Status**: ✅ DONE
- **Checked**: ☑
- **Note**: Full codebase rename from customer_id to interlocutor_id is a separate migration task

### §12.3 ASA mechanic-agnostic
- **Decision**: ASA can configure ANY CognitivePipeline, not just FOCAL.
- **Files updated**:
  - [x] `docs/focal_360/architecture/topics/13-asa-validator.md` - Expanded to mechanic-agnostic meta-agent
- **Status**: ✅ DONE
- **Checked**: ☑

---

## Agent Execution Log

| Agent ID | Task | Status | Docs Updated |
|----------|------|--------|--------------|
| a5514e4 | §1.3 Focal definition | ✅ COMPLETED | overview.md, vision.md, CLAUDE.md |
| a152403 | §3.4+§7.3 api-layer | ✅ COMPLETED | api-layer.md (multimodal + MCP) |
| a9ba542 | §3.5+§4.3 ACF_ARCHITECTURE | ✅ COMPLETED | ACF_ARCHITECTURE.md (tasks + ChannelPolicy) |
| a81247d | §7.3 TOOLBOX_SPEC | ✅ COMPLETED | TOOLBOX_SPEC.md (three-tier model) |
| a3d6a84 | §6.6 InterlocutorChannelPresence | ✅ COMPLETED | customer-profile.md, data_models.md |
| adee38b | §8.0 Interlocutor terminology | ✅ COMPLETED | data_models.md, pipeline.md, domain-model.md |
| a1aeabc | §12.3 ASA mechanic-agnostic | ✅ COMPLETED | 13-asa-validator.md |
| a0c5429 | §4.3 AGENT_RUNTIME_SPEC | ✅ COMPLETED | AGENT_RUNTIME_SPEC.md, 10-channel-capabilities.md |

---

## Verification Checklist

After all updates:
- [x] Grep for "customer_id" - legacy refs remain in older docs (expected), new docs use interlocutor_id
- [x] Grep for inconsistent terminology - interlocutor_id found in updated docs
- [x] Verify ChannelPolicy referenced consistently - found in 9 files including key specs
- [x] Verify task/conversation distinction clear - "Tasks bypass ACF" in ACF_ARCHITECTURE.md
- [x] Cross-reference with architecture_reconsideration.md - all 8 decisions propagated

---

## Summary

**All 8 architectural decisions have been propagated to documentation.**

Key changes made:
1. **FOCAL** is now defined as the alignment CognitivePipeline, not the platform name
2. **Multimodal envelope** added to api-layer.md with content_type + content structure
3. **Tasks bypass ACF** section added showing Agenda→Hatchet TaskWorkflow path
4. **ChannelPolicy** is single source of truth, consolidated in three key docs
5. **InterlocutorChannelPresence** model added for cross-channel awareness
6. **Three-tier tool visibility** model added to TOOLBOX_SPEC.md and api-layer.md
7. **Interlocutor terminology** introduced with InterlocutorType enum
8. **ASA** documented as mechanic-agnostic meta-agent

### Deferred Items
- Full `customer_id` → `interlocutor_id` rename across codebase (separate migration)
- 09-agenda-goals.md and 06-hatchet-integration.md updates (lower priority)
- Remaining §12 gaps (per user request)

---

*Completed: 2025-12-14*
