# Related Products And Projects

Screen Guardian should be designed with an explicit outside-reference loop. The goal is not to copy one product. The goal is to learn reusable patterns for a lightweight, local-first "private vision company" for the main AI: intake fuzzy requests, choose the right visual/audio/browser route, produce compact evidence, and leave heavier models or subagents optional.

## Positioning

Screen Guardian can be understood as a personal perception operations layer for an AI agent.

| Company-like role | Screen Guardian capability |
| --- | --- |
| Intake desk | AI-first tools such as `guardian_check`, `guardian_perceive`, `guardian_prepare_workflow`, and registered commands |
| Field capture team | Screen, region, window, audio, video/audio extraction, delayed capture, render-aware retry, and bounded watch |
| Lab team | Preprocess, OCR routes, image narration routes, video narration routes, audio transcription, and UI/screen parsing adapters |
| Dispatch manager | Decision policies, monitor profiles, extension routes, external API handoff, Codex subagent handoff, and local command bridges |
| Archive clerk | Local cache paths, storage routes, metadata sidecars, hold-file context policy, and audit files |
| QA reviewer | Runtime evaluation, smoke tests, source metadata, confidence fields, and explicit safety boundaries |

The important product claim is not "Screen Guardian sees everything." The stronger claim is: "Screen Guardian helps the main AI request, route, compress, and verify local perception work without forcing one heavy dependency stack."

## Reference Map

| Area | Product or project | User demand it addresses | Strategy worth borrowing | What Screen Guardian should avoid |
| --- | --- | --- | --- | --- |
| Local AI memory | [screenpipe](https://github.com/screenpipe/screenpipe) | Search and summarize what happened on a user's computer across screen and audio history | Event-driven capture, local storage, accessibility tree first, OCR fallback, searchable metadata | Always-on recording as the default mode; make continuous capture opt-in and bounded |
| Screenshot utility | [ShareX](https://github.com/ShareX/ShareX) | Fast screenshot, region capture, annotation, OCR, recording, and flexible destinations | Destination routing, many capture modes, file-first workflow, user-controlled upload paths | Automatic upload defaults; hidden remote destinations |
| Recording engine | [OBS Studio](https://obsproject.com/) | Reliable video/audio recording, streaming, source composition, plugin/script extensibility | Treat capture sources as composable adapters; keep plugin/script routes open for advanced users | Shipping a heavy recorder as the default dependency |
| Browser automation | [Playwright MCP](https://github.com/microsoft/playwright) | Let AI interact with web pages using structured page state instead of screenshots | Accessibility snapshots, stable refs, deterministic click/type operations, screenshots as a fallback | Dumping huge page state into the main context on every step |
| AI browser workflow | [Stagehand](https://github.com/browserbase/stagehand) | Mix natural language with code for production browser automation | Let fuzzy instruction handle unknown pages, but cache repeatable steps and expose structured extraction | Pure vague-agent execution with no repeatable path or preview |
| Vision browser/RPA | [Skyvern](https://github.com/skyvern-ai/skyvern) | Automate messy web workflows that need vision, code, and LLM reasoning | Combine computer vision, code execution, and workflow state; support API and managed/cloud routes | Making Docker/Postgres/cloud API mandatory for a lightweight local plugin |
| Screen parsing | [OmniParser](https://github.com/microsoft/OmniParser) | Convert screenshots into interactable UI element boxes and semantic labels | Add optional screen parser routes that return compact UI element lists for agents | Forcing heavy model weights into the base install |
| OCR | [Tesseract OCR](https://tesseract-ocr.github.io/) | Extract text from images without relying on a remote model | Keep OCR as a replaceable adapter with local-first option and confidence metadata | Assuming OCR is always correct or always installed |
| Computer-use harness | [OpenAI computer use](https://developers.openai.com/api/docs/guides/tools-computer-use) | Let a model inspect UI screenshots and return actions for code to execute | Separate model reasoning from the executor; keep human-in-loop boundaries for risky actions | Treating UI reach as permission to bypass authorization, payment, CAPTCHA, DRM, or privacy expectations |
| Tool protocol | [Model Context Protocol](https://modelcontextprotocol.io/docs/learn/server-concepts) | Give AI apps a standard way to discover tools, resources, and prompts | Keep a stable MCP surface, use resources/prompts for context, and add high-level facades to reduce tool overload | Letting every experimental route appear as a first-use decision for the main AI |

## Borrowed Design Patterns

### 1. Intent Facade First

Many agent tools fail because the main AI must choose among too many low-level tools. Screen Guardian should keep expert tools, but default to intent-shaped entrypoints:

- "look quickly"
- "read this text"
- "capture this window after it renders"
- "watch briefly for a change"
- "hold this file for later"
- "prepare a model/subagent workflow"
- "run a registered capability command"

This matches the lesson from Playwright MCP, Stagehand, and Skyvern: the user or main AI should express the job; the tool should choose the stable route.

### 2. Evidence Packets Instead Of Context Flood

Screen Guardian should return compact evidence packets:

- local path
- metadata sidecar
- source type
- capture timing
- detected likely image type
- preprocessing route
- optional OCR/text summary
- confidence or caveat fields

This borrows from screenpipe's event-plus-metadata model and Playwright's structured page state. Raw images, audio, or video should be held as files unless the main AI actually needs to inspect them.

### 3. Adapter Ladder

Every capability should have an adapter ladder:

1. structured OS/browser data if available
2. lightweight screenshot or audio capture
3. preprocessing or OCR
4. local model route
5. external API route
6. Codex subagent route
7. break-glass local execution

The ladder lets older systems keep working and lets advanced users upgrade routes without forcing everyone onto the heaviest path.

### 4. Fuzzy Instruction Router

The plugin can accept a fuzzy objective, but fuzzy execution should be routed through explicit envelopes or registered commands.

Good shape:

```json
{
  "objective": "Watch this installer until an error appears, then capture the error and prepare a compact explanation request.",
  "routes": ["watch_change", "text_preprocess", "model_request"],
  "budget": {"context": "low", "duration_seconds": 10},
  "delivery": "hold_file"
}
```

Bad shape:

```json
{
  "objective": "Do whatever is needed",
  "execute_anything": true
}
```

Screen Guardian can support powerful work while keeping the work plan inspectable.

### 5. Optional Model And Subagent Backends

The project should leave compatible ports for:

- local OCR
- local vision narration
- remote vision API narration
- video narration API
- audio transcription
- Codex subagent summarization
- local command or script adapters

Each route should declare cost, privacy mode, expected input, expected output, timeout, and whether it is active. Inactive routes should not slow down core capture.

### 6. Continuous Capture As A Bounded Mode

Screenpipe shows the value of event-driven personal history, but Screen Guardian should keep continuous capture as an opt-in workflow profile:

- bounded duration
- bounded frame count
- local-only default
- event trigger visible in metadata
- clear delete/cache behavior
- no hidden scheduler

This preserves the "private vision company" idea without turning the plugin into an always-on surveillance service.

## Product Requirements Derived From The References

| Requirement | Why it matters | Screen Guardian route |
| --- | --- | --- |
| Reduce AI tool-choice load | Too many MCP tools increase context and decision cost | AI-first facade plus registered command catalog |
| Keep visible data local by default | Screen/audio data is sensitive | local cache, hold-file policy, no hidden upload |
| Let fuzzy requests become explicit workflows | Natural language is useful, but unbounded action is risky | workflow envelopes, decision policies, monitor profiles |
| Support older systems and missing dependencies | Users should not lose visual access because one path fails | adapter discovery, robust Python/runtime strategy, optional helper exe |
| Capture after rendering | Slow machines often show blank frames | delay, settle delay, nonblank retry, suspected-unrendered warning |
| Use structured data before pixels when possible | Structured refs are smaller and more reliable | future browser/OS accessibility adapters |
| Use pixels when structure is missing | Games, remote desktops, broken apps, and canvas UIs need vision | screenshot, OCR, screen parser, narration routes |
| Keep heavy work inactive until needed | Audio/video/OCR/model routes can be expensive | persistent feature flags and route activation |
| Evaluate real use, not only contracts | Tool wiring can pass while user outcomes fail | runtime evaluation, optional tiny capture, future model-route tests |

## Immediate Roadmap Implications

1. Add a `guardian_delegate` or `guardian_route_objective` facade later, but keep it prepare-first: it should produce a plan/envelope unless the selected route is a registered safe command.
2. Add browser/page perception as a separate module rather than mixing DOM analysis into the screen-capture core.
3. Add compact evidence packets as a common result shape across screenshot, audio, video, OCR, and narration routes.
4. Add provider descriptors for local models, external APIs, and Codex subagents, with privacy/cost/timeout metadata.
5. Add evaluation scenarios that compare raw screenshot context against preprocessed image, OCR text, UI element list, and model narration.
6. Keep the anti-abuse stance as a project position, not brittle regex policing.

## Boundary

The related-project loop should help Screen Guardian become more useful, not more invasive. The project remains for authorized perception, accessibility, debugging, personal AI assistance, and visibility auditing. It is not designed or supported for bypassing authentication, paywalls, CAPTCHA, DRM, access controls, platform rules, privacy expectations, or unauthorized data access.
