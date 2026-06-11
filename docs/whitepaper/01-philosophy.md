# Philosophy

Screen Guardian exists because desktop perception should not depend on one perfect capture path.

The project starts from a practical failure: an older or constrained Windows system can make native AI screenshot routes unreliable. When that happens, the user's AI loses visual access even though a lighter fallback path may still work.

## Positive Freedom

Screen Guardian expands user agency by giving a personal AI more useful local capabilities:

- discover displays, windows, and capture routes
- capture visible pixels when needed
- save evidence locally for later analysis
- hold large files out of context
- prepare optional model, decision, monitor, audio, video, and webpage workflows

The goal is not to make a heavy recorder. The goal is to give the AI enough perception infrastructure to help the user finish work.

## Negative Freedom

Screen Guardian should not force users into unnecessary upgrades, services, or dependencies:

- no forced Windows upgrade just to try local perception
- no mandatory always-on background service
- no hidden upload
- no hidden scheduler
- no mandatory OCR, browser, audio, video, or model dependency

Optional capabilities can exist, but inactive features should not slow or complicate the active core path.

## AI As Runtime User

Screen Guardian has two users:

- the upstream human who owns the computer and grants authority
- the AI agent that calls tools and spends context

The interface is optimized for the AI runtime user without removing human control. That means structured receipts, explicit side effects, bounded failures, and recommended next actions matter as much as screenshots.

## Core Thesis

The AI should receive a lightweight desktop situation index before it spends context, changes focus, calls a model, or saves an image.

```text
index first -> choose target -> choose observation channel -> apply guard policy -> return receipt
```

This thesis drives the rest of the project structure: scenario cards show where it matters, reference source explains it, optimized runtime performs it, and traceability verifies it.
