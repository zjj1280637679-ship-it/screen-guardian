# Product Models

Screen Guardian is designed to grow through three planned models while keeping the current ultra-light release as the foundation.

## Current: Ultra-light Foundation

The current version is intentionally smaller than the planned product models. It proves the core idea:

- local screenshot access can be exposed through a stable MCP surface
- incompatible native capture paths can have a fallback
- low-resolution images can reduce context pressure
- dependency state can be reported instead of hidden
- project/workflow metadata can mark files before they enter context
- short bounded change detection can catch UI changes without becoming a background recorder
- local image heuristics can choose text/UI/photo preprocessing before optional OCR or narration exists
- runtime limits and storage routes can be changed without rewriting capture tools
- model/program routes can be registered before heavy adapters exist

This stage should stay easy to understand and easy to rewrite.

## Planned Model 1: Lightweight

The Lightweight model should become the dependable daily fallback.

Expected features:

- multiple screenshot adapters behind one stable tool contract
- adapter diagnostics and install hints
- monitor, region, and window presets
- stronger cache cleanup controls
- simple safety prompts for sensitive capture contexts
- richer project/workflow handoff conventions
- presets for common storage routes and runtime-limit profiles

Dependency policy:

- keep dependencies minimal
- prefer pure Python or small native helpers
- make every extra capability optional

## Planned Model 2: Practical

The Practical model should help AI observe short workflows, not only isolated screenshots.

Expected features:

- longer bounded continuous screenshots
- stronger frame-difference detection
- short screen recordings
- OCR for text-heavy screenshots
- image summarization bridge
- optional video summarization bridge
- follow-up question handling for narration or transcription routes
- context-pressure controls such as downscaling and key-frame selection

Dependency policy:

- allow optional FFmpeg or vision helpers
- keep long-running behavior bounded by duration, frame rate, and storage limits
- keep the same adapter result contract where possible

## Planned Model 3: Heavy

The Heavy model is for users who intentionally want a local visual memory or agent workstation.

Expected features:

- longer capture sessions
- OCR and searchable timelines
- app and window filters
- storage policies and retention limits
- subagent routing for image and video interpretation
- local-first visual history tools

Dependency policy:

- heavier dependencies are acceptable only when explicit
- privacy and storage controls become first-class requirements
- no always-on behavior without clear user intent

## Design Rule

Every model should preserve the same principle: expand what the user's AI can do while avoiding forced upgrades, forced background services, and one-path lock-in.
