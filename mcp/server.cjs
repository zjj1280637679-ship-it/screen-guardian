const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const crypto = require("node:crypto");

const SERVER_NAME = "screen-guardian";
const SERVER_VERSION = "0.1.14";
const ROOT = path.resolve(__dirname, "..");
const CAPTURE_SCRIPT_NAME = "screen_guardian_capture.py";
const HELPER_EXE_NAME = "screen-guardian-helper.exe";
const MAX_STDOUT_BYTES = 4 * 1024 * 1024;
const MAX_STDERR_BYTES = 1024 * 1024;
const MIXED_ROOT_BLOCKED_ACTIONS = new Set([
  "set_cache_path",
  "set_storage_routes",
  "set_runtime_limits",
  "set_feature_flags",
  "set_extension_route",
  "set_decision_policy",
  "set_monitor_profile",
  "set_display_name",
  "apply_display_profile",
  "guardian_run_exec",
]);

const imageOutputProperties = {
  output_dir: {
    type: "string",
    description: "Optional local output folder. Overrides the configured cache path for this call.",
  },
  format: {
    type: "string",
    enum: ["png", "jpg"],
    default: "png",
  },
  scale: {
    type: "number",
    description: "Optional scale factor. Bounds are controlled by runtime limits.",
  },
  max_width: {
    type: "integer",
    minimum: 1,
    description: "Optional maximum saved image width.",
  },
  max_height: {
    type: "integer",
    minimum: 1,
    description: "Optional maximum saved image height.",
  },
  quality: {
    type: "integer",
    default: 90,
    description: "JPEG quality when format is jpg. Bounds are controlled by runtime limits.",
  },
  preprocess: {
    type: "string",
    enum: ["none", "auto", "text", "ui", "photo"],
    default: "none",
    description: "Optional local preprocessing preset. text sharpens/grayscales text-heavy captures; auto uses image analysis.",
  },
  settle_delay_ms: {
    type: "integer",
    minimum: 0,
    default: 0,
    description: "Optional delay before capture, useful when an older or slow-rendering program has just opened. Bounds are controlled by runtime limits.",
  },
  delay_seconds: {
    type: "number",
    minimum: 0,
    description: "Human-friendly alias for a pre-capture delay. Converted to settle_delay_ms and bounded by runtime limits.",
  },
  wait_for_nonblank: {
    type: "boolean",
    description: "When true, retry clearly blank captures before saving. Window capture defaults to true when omitted.",
  },
  quiet_preferred: {
    type: "boolean",
    description: "Prefer non-foreground, non-topmost capture when the route supports it. Window capture defaults to quiet-preferred and returns a decision warning before saving visible-screen fallback output.",
  },
  background_mode: {
    type: "string",
    enum: ["best_effort", "strict", "visible_fallback"],
    default: "best_effort",
    description: "Window-only capture strategy. best_effort tries quiet HWND capture and guarded visible fallback, strict requires direct background HWND capture without visible-screen bbox fallback, and visible_fallback explicitly accepts visible-screen fallback behavior.",
  },
  render_guard: {
    type: "string",
    enum: ["save", "warn", "wait", "fail"],
    description: "Protection mode for suspected unrendered blank captures. save keeps old behavior, warn defers saving and returns decision actions, wait retries until nonblank within limits then defers if still blank, and fail blocks blank saves.",
  },
  render_guard_confirmed: {
    type: "boolean",
    default: false,
    description: "Set true only after confirming that a suspected blank/unrendered frame should still be saved.",
  },
  guard_checks: {
    type: "array",
    items: {
      type: "string",
      enum: ["unrendered", "window_client_low_information", "background_capture_unavailable", "minimized_window", "offscreen_window", "tiny_capture", "stale_frame", "occlusion_risk", "bbox_identity_mismatch", "all", "none", "off"],
    },
    description: "Optional capture-quality checks. Defaults to ['unrendered']; other checks are opt-in and return decision actions rather than blocking ordinary capture.",
  },
  allow_unverified_bbox_fallback: {
    type: "boolean",
    default: false,
    description: "Last-resort override for visible-screen bbox window fallback when the topmost-window identity check cannot verify the requested target. Prefer hwnd/exact_title or bringing the target forward.",
  },
  guard_tiny_min_pixels: {
    type: "integer",
    minimum: 1,
    default: 16,
    description: "Minimum width or height used by the optional tiny_capture guard check.",
  },
  render_retry_count: {
    type: "integer",
    minimum: 0,
    default: 2,
    description: "Maximum retries for clearly blank captures. Bounds are controlled by runtime limits.",
  },
  render_retry_interval_ms: {
    type: "integer",
    minimum: 0,
    default: 250,
    description: "Delay between render retries. Bounds are controlled by runtime limits.",
  },
  project_id: {
    type: "string",
    description: "Optional project marker written into the filename and metadata sidecar.",
  },
  workflow_id: {
    type: "string",
    description: "Optional workflow marker written into the filename and metadata sidecar.",
  },
  tags: {
    type: "array",
    items: { type: "string" },
    description: "Optional local tags for the metadata sidecar.",
  },
  note: {
    type: "string",
    description: "Optional note for the metadata sidecar.",
  },
  context_policy: {
    type: "string",
    enum: ["return_path", "hold_file", "analysis_only"],
    default: "return_path",
    description: "Local handoff policy. hold_file marks the file for later use instead of immediate context ingestion.",
  },
  marked_file_only: {
    type: "boolean",
    default: false,
    description: "When true, save and mark the file without treating it as content to read immediately.",
  },
  write_metadata: {
    type: "boolean",
    default: true,
    description: "Write a JSON sidecar with source, workflow, preprocessing, and analysis metadata.",
  },
  source_label: {
    type: "string",
    description: "Optional short label included in the output filename.",
  },
  output_dirs: {
    type: "array",
    items: { type: "string" },
    description: "Optional route list. When output_dir is not set, the first path becomes primary and later paths become mirrors.",
  },
  mirror_dirs: {
    type: "array",
    items: { type: "string" },
    description: "Optional per-call mirror output folders.",
  },
  runtime_limits: {
    type: "object",
    description: "Optional per-call runtime limit overrides. Per-call values can only tighten configured limits, never loosen or remove them.",
    additionalProperties: true,
  },
  feature_flags: {
    type: "object",
    description: "Optional per-call feature flag overrides. Per-call values can only disable features for this call, never enable features disabled in persistent settings.",
    additionalProperties: true,
  },
  analyze: {
    type: "boolean",
    default: false,
    description: "When true, run local heuristic image analysis for this saved capture.",
  },
};

const windowTargetProperties = {
  hwnd: {
    type: "integer",
    description: "Windows HWND. Prefer list_windows first when you do not know it.",
  },
  title_contains: {
    type: "string",
    description: "Match visible windows whose title contains this text. Ambiguous matches require hwnd, exact_title, or allow_first_match.",
  },
  title_contains_any: {
    type: "array",
    items: { type: "string" },
    description: "Pick the first visible window matching any title fragment.",
  },
  exact_title: {
    type: "string",
    description: "Match visible windows whose title exactly matches this string. Multiple exact matches still require hwnd or allow_first_match.",
  },
  process_name: {
    type: "string",
    description: "Match visible windows whose process name contains this text. Ambiguous matches require hwnd, exact_title, or allow_first_match.",
  },
  process_names: {
    type: "array",
    items: { type: "string" },
    description: "Match visible windows matching any process name fragment.",
  },
  allow_first_match: {
    type: "boolean",
    default: false,
    description: "When true, use the first matching window if a filter is ambiguous. Prefer hwnd from list_windows for repeatable captures.",
  },
};

const webpageCaptureProperties = {
  url: {
    type: "string",
    description: "Explicit http, https, or file URL to render and capture.",
  },
  mode: {
    type: "string",
    enum: ["full_page", "viewport", "element", "scroll_container"],
    default: "full_page",
    description: "full_page captures the scrollable document, viewport captures the browser viewport, element captures a CSS selector, and scroll_container stitches an inner scrollable panel.",
  },
  selector: {
    type: "string",
    description: "CSS selector required when mode is element or scroll_container.",
  },
  frame_selector: {
    type: "string",
    description: "Optional iframe CSS selector used before resolving selector, useful for nested embedded pages.",
  },
  viewport_width: {
    type: "integer",
    minimum: 1,
    default: 1440,
    description: "Browser viewport width before capture. Bounds are controlled by runtime limits.",
  },
  viewport_height: {
    type: "integer",
    minimum: 1,
    default: 900,
    description: "Browser viewport height before capture. Bounds are controlled by runtime limits.",
  },
  device_scale_factor: {
    type: "number",
    minimum: 0.1,
    default: 1,
    description: "Browser device scale factor.",
  },
  wait_until: {
    type: "string",
    enum: ["commit", "domcontentloaded", "load", "networkidle"],
    default: "load",
    description: "Playwright navigation wait condition.",
  },
  timeout_ms: {
    type: "integer",
    minimum: 100,
    default: 15000,
    description: "Navigation and screenshot timeout. Bounds are controlled by runtime limits.",
  },
  settle_delay_ms: {
    type: "integer",
    minimum: 0,
    default: 0,
    description: "Optional wait after navigation before capture.",
  },
  delay_seconds: imageOutputProperties.delay_seconds,
  full_page_height_max: {
    type: "integer",
    minimum: 1,
    description: "Decision threshold for very tall full-page captures. Bounds are controlled by runtime limits.",
  },
  allow_oversize: {
    type: "boolean",
    default: false,
    description: "When true, allow full-page capture above full_page_height_max.",
  },
  scroll_axis: {
    type: "string",
    enum: ["vertical"],
    default: "vertical",
    description: "Scroll direction for scroll_container mode. Currently vertical only.",
  },
  max_segments: {
    type: "integer",
    minimum: 1,
    description: "Maximum stitched screenshots for scroll_container mode. Bounds are controlled by runtime limits.",
  },
  segment_delay_ms: {
    type: "integer",
    minimum: 0,
    default: 100,
    description: "Wait after each inner scroll movement before segment capture.",
  },
  format: imageOutputProperties.format,
  quality: imageOutputProperties.quality,
  output_dir: imageOutputProperties.output_dir,
  project_id: imageOutputProperties.project_id,
  workflow_id: imageOutputProperties.workflow_id,
  tags: imageOutputProperties.tags,
  note: imageOutputProperties.note,
  context_policy: imageOutputProperties.context_policy,
  marked_file_only: imageOutputProperties.marked_file_only,
  write_metadata: imageOutputProperties.write_metadata,
  source_label: imageOutputProperties.source_label,
  runtime_limits: imageOutputProperties.runtime_limits,
  feature_flags: imageOutputProperties.feature_flags,
};

const captureChainProperties = {
  objective: {
    type: "string",
    description: "What the guided capture chain is trying to accomplish.",
  },
  route: {
    type: "string",
    enum: ["auto", "desktop", "application", "webpage", "nested_scroll", "mixed"],
    default: "auto",
    description: "Preferred capture route. Use desktop for visible pixels, application for a program window, webpage for browser-rendered pages, and nested_scroll for scrollable panels or iframes.",
  },
  trigger: {
    type: "object",
    additionalProperties: true,
    description: "Declarative trigger such as manual, delay, schedule, screen_change, window_change, selector_visible, error_text, model_feature, audio_feature, or custom.",
  },
  steps: {
    type: "array",
    items: {
      type: "object",
      additionalProperties: true,
    },
    description: "Ordered declarative steps. Preparing a chain writes a local plan only; it does not execute the steps. Runtime rejects steps outside capture, route-sniffing, preprocessing, and prepare-only envelope tools.",
  },
  quiet: {
    type: "boolean",
    default: true,
    description: "Whether the intended route should prefer a quiet/non-topmost path when available.",
  },
  decision_policy_id: {
    type: "string",
    description: "Optional registered decision policy id for callers that later consume the chain envelope.",
  },
  settings: {
    type: "object",
    additionalProperties: true,
    description: "Optional chain settings for a future caller, scheduler, or subagent.",
  },
  output_dir: imageOutputProperties.output_dir,
  project_id: imageOutputProperties.project_id,
  workflow_id: imageOutputProperties.workflow_id,
  tags: imageOutputProperties.tags,
  note: imageOutputProperties.note,
  context_policy: imageOutputProperties.context_policy,
  marked_file_only: imageOutputProperties.marked_file_only,
  write_metadata: imageOutputProperties.write_metadata,
  source_label: imageOutputProperties.source_label,
  runtime_limits: imageOutputProperties.runtime_limits,
  feature_flags: imageOutputProperties.feature_flags,
};

const captureModeProperties = {
  capture_modes: {
    type: "array",
    items: {
      type: "string",
      enum: ["fast", "delay", "wait_render", "wait_buffer", "wait_stable", "wait_error"],
    },
    description: "Stackable AI-first capture modes. Omit for fast direct capture. Use delay, wait_render, wait_buffer/wait_stable, and wait_error only when the caller wants explicit waiting.",
  },
  capture_strategy: {
    type: "string",
    description: "Comma-separated alias for capture_modes, such as 'delay wait_render wait_buffer'.",
  },
  stable_wait_seconds: {
    type: "number",
    minimum: 0,
    default: 2,
    description: "Maximum seconds to wait for wait_buffer/wait_stable before final capture. Bounded by runtime limits.",
  },
  stable_interval_ms: {
    type: "integer",
    minimum: 1,
    default: 250,
    description: "Sampling interval for wait_buffer/wait_stable. Bounded by runtime limits.",
  },
  stable_threshold: {
    type: "number",
    minimum: 0,
    default: 1.5,
    description: "Average pixel-difference threshold below which consecutive samples count as stable.",
  },
  stable_required_samples: {
    type: "integer",
    minimum: 1,
    default: 2,
    description: "Number of consecutive stable comparisons required before final capture.",
  },
  error_wait_seconds: {
    type: "number",
    minimum: 0,
    default: 10,
    description: "Maximum seconds to wait for wait_error before returning an error. Bounded by runtime limits.",
  },
  error_poll_interval_ms: {
    type: "integer",
    minimum: 1,
    default: 500,
    description: "Polling interval for wait_error. Bounded by runtime limits.",
  },
  error_title_contains: {
    type: "string",
    description: "Window-title text that signals an error for wait_error.",
  },
  error_title_contains_any: {
    type: "array",
    items: { type: "string" },
    description: "Any window-title text that signals an error for wait_error.",
  },
  error_process_name: {
    type: "string",
    description: "Process-name text that signals an error for wait_error.",
  },
  error_process_names: {
    type: "array",
    items: { type: "string" },
    description: "Any process-name text that signals an error for wait_error.",
  },
  error_text: {
    type: "string",
    description: "Caller-provided error text used as a title signal in the ultra-light implementation. OCR/DOM error detection belongs to future semantic routes.",
  },
  error_capture_target: {
    type: "string",
    enum: ["original", "matching_window"],
    default: "original",
    description: "When wait_error detects an error window, capture the original target or the matching error window.",
  },
};

const audioCommonProperties = {
  output_dir: imageOutputProperties.output_dir,
  output_dirs: imageOutputProperties.output_dirs,
  mirror_dirs: imageOutputProperties.mirror_dirs,
  project_id: imageOutputProperties.project_id,
  workflow_id: imageOutputProperties.workflow_id,
  tags: imageOutputProperties.tags,
  note: imageOutputProperties.note,
  context_policy: imageOutputProperties.context_policy,
  marked_file_only: imageOutputProperties.marked_file_only,
  write_metadata: imageOutputProperties.write_metadata,
  source_label: imageOutputProperties.source_label,
  runtime_limits: imageOutputProperties.runtime_limits,
  feature_flags: imageOutputProperties.feature_flags,
  analyze: {
    type: "boolean",
    default: false,
    description: "When true, run lightweight local audio analysis after saving.",
  },
};

const guardianTargetProperties = {
  type: {
    type: "string",
    enum: ["screen", "region", "window"],
    default: "screen",
    description: "High-level perception target.",
  },
  display: {
    type: "integer",
    description: "Display index alias for display_index.",
  },
  display_index: {
    type: "integer",
    description: "Display index. Use 0 for the full virtual desktop; 1+ for individual displays.",
  },
  box: {
    type: "object",
    properties: {
      left: { type: "integer" },
      top: { type: "integer" },
      width: { type: "integer", minimum: 1 },
      height: { type: "integer", minimum: 1 },
      relative_to_display: { type: "boolean", default: true },
    },
    additionalProperties: false,
    description: "Region box for a region target.",
  },
  hwnd: windowTargetProperties.hwnd,
  title_contains: windowTargetProperties.title_contains,
  exact_title: windowTargetProperties.exact_title,
  process_name: windowTargetProperties.process_name,
  allow_first_match: windowTargetProperties.allow_first_match,
};

const tools = [
  {
    name: "guardian_check",
    description: "AI-first health check that summarizes runtime, adapters, cache path, capability flags, and recommended next tool.",
    inputSchema: {
      type: "object",
      properties: {
        detail: {
          type: "string",
          enum: ["short", "full"],
          default: "short",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_radar",
    description: "AI-first passive perception radar. Classifies capturable windows and caller-supplied browser page observations into concrete screenshot/page-state routes before any capture, navigation, storage read, or data-layer access.",
    inputSchema: {
      type: "object",
      properties: {
        objective: {
          type: "string",
          description: "What the user wants to learn. Used only for route ranking; no capture or external action is performed.",
        },
        authorization_level: {
          type: "string",
          enum: ["L0_visual_only", "L1_current_page_readonly", "L2_page_interaction", "L3_sensitive_action_confirmed", "L4_sensitive_storage_or_data_access"],
          default: "L0_visual_only",
        },
        declared_permissions: {
          type: "array",
          items: { type: "string" },
          description: "Optional scoped permission words such as screenshot, dom_measure, container_scroll, file_convert, export_download, api_readonly, database_readonly, or registry_readonly.",
        },
        target: {
          type: "object",
          properties: {
            kind: { type: "string", enum: ["unknown", "screen", "window", "browser_tab", "webpage", "file", "folder", "api", "database", "registry"] },
            title: { type: "string" },
            url: { type: "string" },
            selector: { type: "string" },
            frame_selector: { type: "string" },
            path: { type: "string" },
          },
          additionalProperties: false,
          description: "Optional target hint. Hints are classified, not treated as authorization or proof of state.",
        },
        current_pages: {
          type: "array",
          items: {
            type: "object",
            additionalProperties: true,
            properties: {
              title: { type: "string" },
              url: { type: "string" },
              source: { type: "string" },
              viewport: { type: "object", additionalProperties: true },
              documentSize: { type: "object", additionalProperties: true },
              scrollables: { type: "array", items: { type: "object", additionalProperties: true } },
              iframe_count: { type: "integer" },
              table_count: { type: "integer" },
              pagination: { type: "object", additionalProperties: true },
              requires_session: { type: "boolean" },
            },
          },
          description: "Readonly page observations from a browser connector: title/url, viewport/document size, scrollable containers, iframe/table/pagination hints. Do not include cookies, localStorage, sessionStorage, passwords, or secrets.",
        },
        page_observations: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Alias for current_pages.",
        },
        open_tabs: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Optional browser open-tab metadata. Title/URL-only tabs are marked as needing one readonly DOM measurement before route selection.",
        },
        url: {
          type: "string",
          description: "Optional explicit webpage URL to include in page target planning.",
        },
        urls: {
          type: "array",
          items: { type: "string" },
        },
        pages: {
          type: "array",
          items: {
            type: "object",
            properties: {
              url: { type: "string" },
              label: { type: "string" },
              mode: { type: "string", enum: ["full_page", "viewport", "element", "scroll_container"] },
              selector: { type: "string" },
              frame_selector: { type: "string" },
            },
            required: ["url"],
            additionalProperties: true,
          },
        },
        include_capture_targets: {
          type: "boolean",
          default: true,
          description: "Include the no-screenshot display/window/page target index.",
        },
        include_displays: {
          type: "boolean",
          default: true,
        },
        include_windows: {
          type: "boolean",
          default: true,
        },
        include_pages: {
          type: "boolean",
          default: true,
        },
        include_visibility_probe: {
          type: "boolean",
          default: true,
          description: "Sample topmost windows at target-window points to classify possible occlusion without capturing pixels.",
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 200,
          default: 50,
        },
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_extract_page_facts",
    description: "AI-first readonly page object/fact extractor. Turns caller-supplied page observations into valuable object handles, dangerous object handles, and redacted structured facts before any screenshot, navigation, browser-storage read, or data-layer access.",
    inputSchema: {
      type: "object",
      properties: {
        objective: {
          type: "string",
          description: "What the user wants to learn. Used only to label extraction intent; no page action is performed.",
        },
        intent: {
          type: "string",
          enum: ["general", "api_settings", "credentials_console", "docs", "pricing", "model_catalog"],
          default: "general",
        },
        authorization_level: {
          type: "string",
          enum: ["L0_visual_only", "L1_current_page_readonly", "L2_page_interaction", "L3_sensitive_action_confirmed", "L4_sensitive_storage_or_data_access"],
          default: "L1_current_page_readonly",
        },
        declared_permissions: {
          type: "array",
          items: { type: "string" },
          description: "Optional scoped permission words such as dom_measure, container_scroll, screenshot, table_read, or form_metadata_read. This tool performs none of those actions itself.",
        },
        privacy_mode: {
          type: "string",
          enum: ["redact_secrets", "metadata_only"],
          default: "redact_secrets",
          description: "redact_secrets is the normal mode. Raw API keys, bearer tokens, and secret-like values must not be emitted.",
        },
        target: {
          type: "object",
          properties: {
            kind: { type: "string", enum: ["unknown", "browser_tab", "webpage", "console", "document"] },
            title: { type: "string" },
            url: { type: "string" },
          },
          additionalProperties: false,
        },
        current_pages: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Readonly page observations from a browser connector: title/url, viewport/document size, scrollables, headings, links, article text, blocks, tables, rows, controls, or forms. Do not include cookies, localStorage, sessionStorage, passwords, or raw secrets.",
        },
        page_observations: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Alias for current_pages.",
        },
        documents: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Readonly extracted article/document snippets supplied by the caller.",
        },
        extracted_pages: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Readonly extracted page snippets supplied by the caller.",
        },
        article_pages: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Readonly article-like page snippets supplied by the caller.",
        },
        console_pages: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Readonly console/admin page snippets supplied by the caller. Sensitive values should already be omitted or masked; this tool redacts again.",
        },
        text: {
          type: "string",
          description: "Optional inline readonly text observation.",
        },
        title: {
          type: "string",
        },
        url: {
          type: "string",
        },
        blocks: {
          type: "array",
          items: { type: "string" },
        },
        rows: {
          type: "array",
          items: { type: "string" },
        },
        controls: {
          type: "array",
          items: { type: "object", additionalProperties: true },
        },
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_capture_targets",
    description: "AI-first pre-capture target index. Lists displays, capturable application windows, and optional webpage capture targets with recommended quiet/background capture arguments before any screenshot is taken.",
    inputSchema: {
      type: "object",
      properties: {
        include_displays: {
          type: "boolean",
          default: true,
          description: "Include display/desktop capture targets.",
        },
        include_windows: {
          type: "boolean",
          default: true,
          description: "Include visible application windows with HWND-backed capture arguments.",
        },
        include_pages: {
          type: "boolean",
          default: true,
          description: "Include explicit webpage URL targets supplied by url, urls, or pages. Browser tab enumeration is not performed by this local helper.",
        },
        url: {
          type: "string",
          description: "Optional single webpage URL to include as a page target.",
        },
        urls: {
          type: "array",
          items: { type: "string" },
          description: "Optional webpage URLs to include as page targets.",
        },
        pages: {
          type: "array",
          items: {
            type: "object",
            properties: {
              url: { type: "string" },
              label: { type: "string" },
              mode: { type: "string", enum: ["full_page", "viewport", "element", "scroll_container"] },
              selector: { type: "string" },
              frame_selector: { type: "string" },
            },
            required: ["url"],
            additionalProperties: false,
          },
          description: "Optional structured page targets for webpage capture.",
        },
        title_contains: windowTargetProperties.title_contains,
        title_contains_any: windowTargetProperties.title_contains_any,
        exact_title: windowTargetProperties.exact_title,
        process_name: windowTargetProperties.process_name,
        process_names: windowTargetProperties.process_names,
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 200,
          default: 50,
          description: "Maximum windows to include in the target index.",
        },
        include_visibility_probe: {
          type: "boolean",
          default: true,
          description: "Sample topmost windows at target-window points to report possible occlusion risk without capturing an image.",
        },
        background_mode: {
          ...imageOutputProperties.background_mode,
          default: "strict",
          description: "Preferred background mode for returned window capture target args. Defaults to strict for occlusion-resistant HWND capture without visible-screen bbox fallback.",
        },
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_sniff_context",
    description: "AI-first authorized route-sniffing layer. Recommends the most efficient safe perception/data routes from declared authorization without capturing pixels, reading secrets, or touching databases/registries.",
    inputSchema: {
      type: "object",
      properties: {
        objective: {
          type: "string",
          description: "What the user wants to accomplish. Used only to rank routes; no external action is performed.",
        },
        authorization_level: {
          type: "string",
          enum: ["L0_visual_only", "L1_current_page_readonly", "L2_page_interaction", "L3_sensitive_action_confirmed", "L4_sensitive_storage_or_data_access"],
          default: "L0_visual_only",
          description: "Explicit user authorization envelope. Higher levels only recommend routes; they do not execute sensitive actions.",
        },
        declared_permissions: {
          type: "array",
          items: { type: "string" },
          description: "Optional user-declared permissions such as dom_measure, container_scroll, screenshot, export_download, file_convert, api_readonly, database_readonly, or registry_readonly.",
        },
        target: {
          type: "object",
          properties: {
            kind: { type: "string", enum: ["unknown", "screen", "window", "browser_tab", "webpage", "file", "folder", "api", "database", "registry"] },
            title: { type: "string" },
            url: { type: "string" },
            selector: { type: "string" },
            frame_selector: { type: "string" },
            path: { type: "string" },
          },
          additionalProperties: false,
          description: "Optional current target hint. The sniffer treats it as a hint, not proof of authorization.",
        },
        file_paths: {
          type: "array",
          items: { type: "string" },
          description: "Optional local files to classify by metadata and extension only. Contents are not read.",
        },
        url: {
          type: "string",
          description: "Optional webpage URL hint for route planning.",
        },
        urls: {
          type: "array",
          items: { type: "string" },
          description: "Optional webpage URL hints.",
        },
        include_capture_targets: {
          type: "boolean",
          default: false,
          description: "When true, include the normal guardian_capture_targets index. This still performs no screenshot.",
        },
        include_document_routes: {
          type: "boolean",
          default: true,
          description: "Include document-to-markdown and file-conversion route recommendations for supplied file paths.",
        },
        allow_network_file_metadata_probe: {
          type: "boolean",
          default: false,
          description: "Opt in to metadata probing for UNC or file:// paths. Defaults false so route sniffing does not touch potential network paths.",
        },
        include_sensitive_routes: {
          type: "boolean",
          default: false,
          description: "Include high-risk API/database/registry route candidates as blocked-or-confirmation-required options.",
        },
        data_layer_user_consented: {
          type: "boolean",
          default: false,
          description: "When true, the sniffer can consider scoped data-layer routes. Eligibility still requires data_layer_consent_text and a concrete scoped target.",
        },
        data_layer_consent_text: {
          type: "string",
          description: "Consent/audit text for data-layer route readiness. Without it, scoped routes remain scope-ready rather than eligible.",
        },
        data_layer_scope: {
          type: "object",
          additionalProperties: true,
          description: "Proposed data-layer scope used only for route status. Must include a concrete target such as endpoint, connection_ref, registry_key, export_name, file_path, app_id, or tables; row_limit/fields/where are constraints, not targets by themselves.",
        },
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_perceive",
    description: "AI-first perception facade for quick screen looks, text/UI captures, window capture, bounded watch, or hold-file context control.",
    inputSchema: {
      type: "object",
      properties: {
        task: {
          type: "string",
          enum: ["quick_look", "read_text", "debug_ui", "capture_window", "watch_change", "hold_file"],
          default: "quick_look",
        },
        target: {
          type: "object",
          properties: guardianTargetProperties,
          additionalProperties: false,
          description: "Screen, region, or window target. Defaults to the primary display.",
        },
        context_budget: {
          type: "string",
          enum: ["low", "normal", "high", "hold_file"],
          default: "normal",
        },
        output_dir: imageOutputProperties.output_dir,
        source_label: imageOutputProperties.source_label,
        ...captureModeProperties,
        delay_seconds: imageOutputProperties.delay_seconds,
        settle_delay_ms: imageOutputProperties.settle_delay_ms,
        wait_for_nonblank: imageOutputProperties.wait_for_nonblank,
        quiet_preferred: imageOutputProperties.quiet_preferred,
        background_mode: imageOutputProperties.background_mode,
        render_guard: imageOutputProperties.render_guard,
        render_guard_confirmed: imageOutputProperties.render_guard_confirmed,
        allow_unverified_bbox_fallback: imageOutputProperties.allow_unverified_bbox_fallback,
        guard_checks: imageOutputProperties.guard_checks,
        render_retry_count: imageOutputProperties.render_retry_count,
        render_retry_interval_ms: imageOutputProperties.render_retry_interval_ms,
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        tags: imageOutputProperties.tags,
        note: imageOutputProperties.note,
        duration_seconds: {
          type: "number",
          minimum: 0.1,
          description: "Optional bounded watch duration when task is watch_change.",
        },
        interval_seconds: {
          type: "number",
          description: "Optional bounded watch interval when task is watch_change.",
        },
        change_threshold: {
          type: "number",
          minimum: 0,
          description: "Optional change threshold when task is watch_change.",
        },
        max_captures: {
          type: "integer",
          minimum: 1,
          description: "Optional maximum captures when task is watch_change.",
        },
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_survey_windows",
    description: "AI-first multi-window survey. Lists visible program-window status and can save a bounded set of quiet local window captures for selective review.",
    inputSchema: {
      type: "object",
      properties: {
        capture_mode: {
          type: "string",
          enum: ["status_only", "hold_file", "return_paths"],
          default: "status_only",
          description: "status_only only reports windows. hold_file saves bounded captures as marked local files. return_paths saves bounded captures and returns paths for optional immediate review.",
        },
        limit: {
          type: "integer",
          minimum: 1,
          default: 50,
          description: "Maximum windows to report. Bounded by runtime limits.",
        },
        capture_limit: {
          type: "integer",
          minimum: 0,
          default: 0,
          description: "Maximum windows to capture when capture_mode is not status_only. Bounded by runtime limits.",
        },
        capture_selection: {
          type: "string",
          enum: ["first_n", "ready_only", "suspected_problem"],
          default: "first_n",
          description: "Which reported windows should be captured first.",
        },
        include_visibility_probe: {
          type: "boolean",
          default: true,
          description: "Sample topmost windows at target-window points to flag likely occlusion without taking a screenshot.",
        },
        hwnd: windowTargetProperties.hwnd,
        hwnds: {
          type: "array",
          items: { type: "integer" },
          description: "Optional explicit HWND list to survey or capture.",
        },
        title_contains: windowTargetProperties.title_contains,
        title_contains_any: windowTargetProperties.title_contains_any,
        exact_title: windowTargetProperties.exact_title,
        process_name: windowTargetProperties.process_name,
        process_names: windowTargetProperties.process_names,
        context_budget: {
          type: "string",
          enum: ["low", "normal", "high", "hold_file"],
          default: "low",
          description: "Batch image budget. low defaults to smaller images; hold_file marks saved captures for later review.",
        },
        output_dir: imageOutputProperties.output_dir,
        source_label: imageOutputProperties.source_label,
        format: imageOutputProperties.format,
        scale: imageOutputProperties.scale,
        max_width: imageOutputProperties.max_width,
        max_height: imageOutputProperties.max_height,
        quality: imageOutputProperties.quality,
        preprocess: imageOutputProperties.preprocess,
        analyze: imageOutputProperties.analyze,
        delay_seconds: imageOutputProperties.delay_seconds,
        settle_delay_ms: imageOutputProperties.settle_delay_ms,
        wait_for_nonblank: imageOutputProperties.wait_for_nonblank,
        quiet_preferred: imageOutputProperties.quiet_preferred,
        background_mode: imageOutputProperties.background_mode,
        render_guard: imageOutputProperties.render_guard,
        render_guard_confirmed: imageOutputProperties.render_guard_confirmed,
        allow_unverified_bbox_fallback: imageOutputProperties.allow_unverified_bbox_fallback,
        guard_checks: imageOutputProperties.guard_checks,
        render_retry_count: imageOutputProperties.render_retry_count,
        render_retry_interval_ms: imageOutputProperties.render_retry_interval_ms,
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        tags: imageOutputProperties.tags,
        note: imageOutputProperties.note,
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_prepare_workflow",
    description: "AI-first workflow facade that prepares local model, decision, monitor, capture-chain, or consented data-layer envelopes without executing external routes.",
    inputSchema: {
      type: "object",
      properties: {
        workflow_type: {
          type: "string",
          enum: ["model_request", "decision_request", "monitor_tick", "capture_chain", "data_layer_request"],
        },
        source_path: {
          type: "string",
          description: "Optional local file path used as workflow input.",
        },
        objective: {
          type: "string",
          description: "What this workflow is trying to accomplish.",
        },
        settings: {
          type: "object",
          additionalProperties: true,
          description: "Optional model, decision, or monitor settings.",
        },
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        output_dir: imageOutputProperties.output_dir,
        route_id: {
          type: "string",
          description: "Optional registered extension route id for model requests.",
        },
        policy_id: {
          type: "string",
          description: "Optional registered decision policy id.",
        },
        profile_id: {
          type: "string",
          description: "Optional registered monitor profile id.",
        },
        route: captureChainProperties.route,
        trigger: captureChainProperties.trigger,
        steps: captureChainProperties.steps,
        quiet: captureChainProperties.quiet,
        decision_policy_id: captureChainProperties.decision_policy_id,
        source_type: {
          type: "string",
          enum: ["database", "registry", "api", "page_export", "file", "app_storage"],
          description: "Data source type for workflow_type=data_layer_request.",
        },
        data_source_type: {
          type: "string",
          enum: ["database", "registry", "api", "page_export", "file", "app_storage"],
          description: "Alias for source_type when workflow_type=data_layer_request.",
        },
        operation: {
          type: "string",
          enum: ["inspect_schema", "read", "query", "export", "write", "update", "delete", "migrate", "permission_change"],
          description: "Data-layer operation for workflow_type=data_layer_request.",
        },
        scope: {
          type: "object",
          additionalProperties: true,
          description: "Explicit data-layer scope. Must include a concrete target such as connection_ref, tables, registry_key, endpoint, export_name, file_path, or app_id; fields/where/row_limit only constrain that target.",
        },
        query: { type: "string" },
        action_plan: { type: "array", items: { type: "object", additionalProperties: true } },
        user_consented: {
          type: "boolean",
          default: false,
          description: "Must be true before a data-layer request envelope can be prepared.",
        },
        consent_text: {
          type: "string",
          description: "User-facing consent text stored in the audit envelope.",
        },
        reason: { type: "string" },
        actor: { type: "string" },
        expires_at: { type: "string" },
        mutation_confirmed: {
          type: "boolean",
          default: false,
          description: "Required for mutating data-layer operations.",
        },
        backup_plan: { type: "string" },
        rollback_plan: { type: "string" },
        dry_run_first: { type: "boolean", default: true },
        connection_ref: { type: "string" },
        registry_key: { type: "string" },
        api_endpoint: { type: "string" },
        file_path: { type: "string" },
        export_name: { type: "string" },
        app_id: { type: "string" },
        tables: { type: "array", items: { type: "string" } },
        fields: { type: "array", items: { type: "string" } },
        where: { type: "string" },
        row_limit: { type: "integer", minimum: 1 },
      },
      required: ["workflow_type"],
      additionalProperties: false,
    },
  },
  {
    name: "guardian_list_commands",
    description: "List reusable AI capability runtime commands so the main AI can choose an intent without guessing low-level tools.",
    inputSchema: {
      type: "object",
      properties: {
        category: {
          type: "string",
          enum: ["diagnostic", "perceive", "artifact", "workflow", "emergency"],
          description: "Optional command category filter.",
        },
        include_disabled: {
          type: "boolean",
          default: true,
          description: "Include commands whose required feature flags are currently inactive.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "guardian_run_command",
    description: "Run a registered capability command only; this does not accept arbitrary shell or code strings.",
    inputSchema: {
      type: "object",
      properties: {
        command_id: {
          type: "string",
          description: "Registered command id from guardian_list_commands.",
        },
        args: {
          type: "object",
          additionalProperties: true,
          description: "Command arguments merged with the command defaults.",
        },
      },
      required: ["command_id"],
      additionalProperties: false,
    },
  },
  {
    name: "guardian_prepare_exec",
    description: "Prepare a local break-glass execution envelope without running code.",
    inputSchema: {
      type: "object",
      properties: {
        language: {
          type: "string",
          enum: ["python", "powershell", "node"],
          default: "python",
        },
        code: {
          type: "string",
          description: "Local code snippet to save in a prepared execution envelope.",
        },
        cwd: {
          type: "string",
          description: "Optional working directory for later execution.",
        },
        timeout_seconds: {
          type: "number",
          minimum: 0.1,
          default: 30,
        },
        reason: {
          type: "string",
          description: "User-facing reason for this break-glass request.",
        },
        expected_output: {
          type: "string",
          description: "Optional expected result or success signal.",
        },
        risk_note: {
          type: "string",
          description: "Optional risk note for the user/audit trail.",
        },
        output_dir: imageOutputProperties.output_dir,
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        tags: imageOutputProperties.tags,
        note: imageOutputProperties.note,
      },
      required: ["code"],
      additionalProperties: false,
    },
  },
  {
    name: "guardian_run_exec",
    description: "Run explicit break-glass local code. Requires persistent raw_local_exec feature enablement and user_confirmed=true.",
    inputSchema: {
      type: "object",
      properties: {
        envelope_path: {
          type: "string",
          description: "Optional prepared execution envelope path.",
        },
        language: {
          type: "string",
          enum: ["python", "powershell", "node"],
          default: "python",
        },
        code: {
          type: "string",
          description: "Local code snippet to execute when envelope_path is not provided.",
        },
        cwd: {
          type: "string",
          description: "Working directory for execution.",
        },
        timeout_seconds: {
          type: "number",
          minimum: 0.1,
          default: 30,
        },
        user_confirmed: {
          type: "boolean",
          default: false,
          description: "Must be true for every raw execution call.",
        },
        reason: {
          type: "string",
          description: "User-facing reason for this execution.",
        },
        output_dir: imageOutputProperties.output_dir,
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        tags: imageOutputProperties.tags,
        note: imageOutputProperties.note,
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      required: ["user_confirmed"],
      additionalProperties: false,
    },
  },
  {
    name: "list_capture_routes",
    description: "List the desktop, application, webpage, nested-scroll, and guided-chain capture routes with quiet-capture guidance.",
    inputSchema: {
      type: "object",
      properties: {
        include_examples: {
          type: "boolean",
          default: true,
          description: "Include compact example tool calls for each route.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_capture_chain",
    description: "Prepare a local guided capture-chain envelope for conditional screenshots, quiet webpage capture, preprocessing, or later model handoff without executing it.",
    inputSchema: {
      type: "object",
      properties: captureChainProperties,
      required: ["objective"],
      additionalProperties: false,
    },
  },
  {
    name: "check_dependencies",
    description: "Check local Python screenshot dependencies, adapters, and cache location.",
    inputSchema: {
      type: "object",
      properties: {
        output_dir: {
          type: "string",
          description: "Optional local folder for this dependency/cache check.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "get_runtime_settings",
    description: "Read local Screen Guardian settings, including configured cache path and display profile.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
  },
  {
    name: "set_cache_path",
    description: "Set or clear the persistent local cache folder for captures.",
    inputSchema: {
      type: "object",
      properties: {
        cache_dir: {
          type: "string",
          description: "Persistent local cache folder. Pass an empty string to return to the default Pictures/ScreenGuardian path.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_storage_routes",
    description: "Set persistent primary cache and extra mirror output folders.",
    inputSchema: {
      type: "object",
      properties: {
        cache_dir: {
          type: "string",
          description: "Persistent primary cache folder. Pass an empty string to return to the default.",
        },
        extra_output_dirs: {
          type: "array",
          items: { type: "string" },
          description: "Persistent mirror folders. Captures are copied there after the primary save.",
        },
        clear_extra_output_dirs: {
          type: "boolean",
          default: false,
          description: "Clear persistent mirror folders.",
        },
        create_dirs: {
          type: "boolean",
          default: true,
          description: "Create configured folders when possible.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_runtime_limits",
    description: "Set, remove, or reset configurable bounds such as watch duration, capture count, scale, and JPEG quality.",
    inputSchema: {
      type: "object",
      properties: {
        reset: {
          type: "boolean",
          default: false,
          description: "Reset limits to ultra-light defaults before applying updates.",
        },
        limits: {
          type: "object",
          description: "Limit updates. Use null, 'none', or 'unbounded' to remove a configurable bound.",
          additionalProperties: true,
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_feature_flags",
    description: "Enable, disable, or reset optional capability modules so inactive features do not run optional work.",
    inputSchema: {
      type: "object",
      properties: {
        reset: {
          type: "boolean",
          default: false,
          description: "Reset feature flags to defaults before applying updates.",
        },
        flags: {
          type: "object",
          description: "Feature flag updates such as image_analysis:false or video_narration_routes:true.",
          additionalProperties: true,
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "list_extension_routes",
    description: "List registered judgment, OCR, image narration, video narration, transcription, or custom adapter routes.",
    inputSchema: {
      type: "object",
      properties: {
        role: {
          type: "string",
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "audio_summary", "sound_diagnostics", "transcription", "custom"],
          description: "Optional role filter.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_extension_route",
    description: "Register, update, disable, or remove a model/program route for future judgment, OCR, or narration adapters.",
    inputSchema: {
      type: "object",
      properties: {
        id: {
          type: "string",
          description: "Stable route id.",
        },
        route_id: {
          type: "string",
          description: "Alias for id.",
        },
        role: {
          type: "string",
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "audio_summary", "sound_diagnostics", "transcription", "custom"],
          default: "vision_summary",
        },
        enabled: {
          type: "boolean",
          default: true,
        },
        handoff_mode: {
          type: "string",
          enum: ["prepared_file", "external_api", "codex_subagent", "local_command"],
          default: "prepared_file",
          description: "How a future adapter should hand off this route. Ultra-light mode only records this choice.",
        },
        provider: {
          type: "string",
          description: "Provider or adapter family name.",
        },
        model: {
          type: "string",
          description: "Model name or local adapter model id.",
        },
        endpoint: {
          type: "string",
          description: "Optional endpoint for a future adapter bridge.",
        },
        api_key_env: {
          type: "string",
          description: "Optional environment-variable name that a future external API bridge can read.",
        },
        command: {
          type: "string",
          description: "Optional local command descriptor for a future adapter bridge. Ultra-light mode does not execute it.",
        },
        capabilities: {
          type: "array",
          items: { type: "string" },
          description: "Optional route capabilities, such as keyframes, timestamps, ocr, or followups.",
        },
        settings: {
          type: "object",
          description: "Route defaults such as temperature, quality, max_tokens, detail, or language.",
          additionalProperties: true,
        },
        notes: {
          type: "string",
        },
        remove: {
          type: "boolean",
          default: false,
          description: "Remove the route matching id/route_id.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_model_request",
    description: "Write a local request envelope for an external judgment/OCR/narration/transcription model, including follow-up questions and settings.",
    inputSchema: {
      type: "object",
      properties: {
        route_id: {
          type: "string",
          description: "Optional registered extension route id.",
        },
        role: {
          type: "string",
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "audio_summary", "sound_diagnostics", "transcription", "custom"],
          default: "vision_summary",
        },
        path: {
          type: "string",
          description: "Optional image/video/audio/local file path for the model request.",
        },
        prompt: {
          type: "string",
          description: "Primary model instruction.",
        },
        followup_of: {
          type: "string",
          description: "Optional prior request or response id/path this question follows.",
        },
        questions: {
          type: "array",
          items: { type: "string" },
          description: "Follow-up questions for the narration/transcription model.",
        },
        settings: {
          type: "object",
          description: "Per-request settings such as temperature, quality, max_tokens, detail, or language.",
          additionalProperties: true,
        },
        ...imageOutputProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_data_layer_request",
    description: "Write a local consent envelope for a scoped data-layer request. Requires user_consented=true and explicit scope; it does not query, mutate, export, upload, or read the data layer.",
    inputSchema: {
      type: "object",
      properties: {
        source_type: {
          type: "string",
          enum: ["database", "registry", "api", "page_export", "file", "app_storage"],
          description: "The data-layer family being requested.",
        },
        data_source_type: {
          type: "string",
          enum: ["database", "registry", "api", "page_export", "file", "app_storage"],
          description: "Alias for source_type.",
        },
        operation: {
          type: "string",
          enum: ["inspect_schema", "read", "query", "export", "write", "update", "delete", "migrate", "permission_change"],
          default: "read",
        },
        objective: { type: "string" },
        scope: {
          type: "object",
          additionalProperties: true,
          description: "Explicit scope. Must include a concrete target such as connection_ref, tables, registry_key, api_endpoint, file_path, export_name, or app_id; fields/where/row_limit only constrain that target.",
        },
        query: {
          type: "string",
          description: "Optional readonly query or proposed query text. Inline secrets are rejected.",
        },
        action_plan: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Optional proposed data-layer steps for later executor review.",
        },
        user_consented: {
          type: "boolean",
          default: false,
          description: "Required true. This prepares an audit envelope but still does not execute the data-layer action.",
        },
        consent_text: {
          type: "string",
          description: "Required user-facing consent statement for the audit envelope.",
        },
        reason: {
          type: "string",
          description: "Alias/fallback for consent_text.",
        },
        actor: { type: "string", default: "user" },
        expires_at: { type: "string" },
        mutation_confirmed: {
          type: "boolean",
          default: false,
          description: "Required for write/update/delete/migrate/permission_change requests.",
        },
        backup_plan: { type: "string" },
        rollback_plan: { type: "string" },
        dry_run_first: {
          type: "boolean",
          default: true,
        },
        connection_ref: { type: "string" },
        registry_key: { type: "string" },
        api_endpoint: { type: "string" },
        file_path: { type: "string" },
        export_name: { type: "string" },
        app_id: { type: "string" },
        tables: { type: "array", items: { type: "string" } },
        fields: { type: "array", items: { type: "string" } },
        where: { type: "string" },
        row_limit: { type: "integer", minimum: 1 },
        settings: { type: "object", additionalProperties: true },
        output_dir: imageOutputProperties.output_dir,
        project_id: imageOutputProperties.project_id,
        workflow_id: imageOutputProperties.workflow_id,
        tags: imageOutputProperties.tags,
        note: imageOutputProperties.note,
        runtime_limits: imageOutputProperties.runtime_limits,
        feature_flags: imageOutputProperties.feature_flags,
      },
      required: ["user_consented", "consent_text"],
      additionalProperties: false,
    },
  },
  {
    name: "list_decision_policies",
    description: "List configurable decision policies for choosing capture, preprocessing, storage, model route, or monitor actions.",
    inputSchema: {
      type: "object",
      properties: {
        role: {
          type: "string",
          description: "Optional role filter, such as capture_decision, monitor_decision, or model_route_decision.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_decision_policy",
    description: "Register, update, or remove an arbitrary-complexity decision policy or function route.",
    inputSchema: {
      type: "object",
      properties: {
        id: { type: "string", description: "Stable decision policy id." },
        policy_id: { type: "string", description: "Alias for id." },
        role: { type: "string", default: "capture_decision" },
        enabled: { type: "boolean", default: true },
        mode: {
          type: "string",
          enum: ["manual", "rule_table", "scoring_function", "function_route", "prepared_file", "codex_subagent", "external_api", "local_command"],
          default: "function_route",
          description: "How the policy decides. Arbitrary complexity belongs behind function_route/API/subagent/local command adapters.",
        },
        route_id: {
          type: "string",
          description: "Optional extension route used by this decision policy.",
        },
        objective: {
          type: "string",
          description: "Human-readable objective the decision function optimizes.",
        },
        input_schema: { type: "object", additionalProperties: true },
        output_schema: { type: "object", additionalProperties: true },
        rules: { type: "array", items: { type: "object", additionalProperties: true } },
        candidates: { type: "array", items: { type: "object", additionalProperties: true } },
        constraints: { type: "array", items: { type: "object", additionalProperties: true } },
        settings: { type: "object", additionalProperties: true },
        notes: { type: "string" },
        remove: { type: "boolean", default: false },
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_decision_request",
    description: "Write a local decision-request envelope for an arbitrary-complexity policy, route, API, subagent, or caller.",
    inputSchema: {
      type: "object",
      properties: {
        policy_id: { type: "string", description: "Optional registered decision policy id." },
        role: { type: "string", default: "capture_decision" },
        objective: { type: "string" },
        observation: { type: "object", additionalProperties: true },
        candidates: { type: "array", items: { type: "object", additionalProperties: true } },
        constraints: { type: "array", items: { type: "object", additionalProperties: true } },
        settings: { type: "object", additionalProperties: true },
        ...audioCommonProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "list_monitor_profiles",
    description: "List periodic or feature-triggered monitor profiles for webpages, programs, screens, audio, video, errors, or model-detected features.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "string", description: "Optional project filter." },
      },
      additionalProperties: false,
    },
  },
  {
    name: "set_monitor_profile",
    description: "Register, update, or remove a periodic/feature-triggered monitor profile.",
    inputSchema: {
      type: "object",
      properties: {
        id: { type: "string", description: "Stable monitor profile id." },
        profile_id: { type: "string", description: "Alias for id." },
        enabled: { type: "boolean", default: true },
        project_id: { type: "string" },
        workflow_id: { type: "string" },
        media: {
          type: "array",
          items: { type: "string" },
          description: "Media channels such as screen, window, webpage, video, audio, or custom.",
        },
        schedule: {
          type: "object",
          description: "Schedule descriptor, for example {mode:'periodic', interval_seconds:60}.",
          additionalProperties: true,
        },
        interval_seconds: {
          type: "number",
          description: "Shortcut used when schedule is omitted.",
        },
        targets: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Targets such as webpage URL, window title, process name, region, audio device, or video file.",
        },
        triggers: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Triggers such as periodic, visual_change, web_change, error_text, model_feature, audio_energy, audio_silence, or audio_clipping.",
        },
        actions: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Actions such as capture_screen, capture_window, record_audio, extract_audio_track, prepare_model_request, or prepare_decision_request.",
        },
        decision_policy_id: { type: "string" },
        settings: { type: "object", additionalProperties: true },
        notes: { type: "string" },
        remove: { type: "boolean", default: false },
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_monitor_tick",
    description: "Write a local monitor-tick envelope for a scheduler/caller/future adapter to process one periodic or feature-triggered cycle.",
    inputSchema: {
      type: "object",
      properties: {
        profile_id: { type: "string", description: "Optional registered monitor profile id." },
        observations: {
          type: "object",
          description: "Current observations, such as DOM hash, window state, error text, audio metrics, or model feature results.",
          additionalProperties: true,
        },
        detected_features: {
          type: "array",
          items: { type: "object", additionalProperties: true },
          description: "Features detected by a program, route, or agent model.",
        },
        candidate_actions: {
          type: "array",
          items: { type: "object", additionalProperties: true },
        },
        ...audioCommonProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "get_display_profile",
    description: "Read the active localized or manual display name profile.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
  },
  {
    name: "set_display_name",
    description: "Set display-name mode to system-language auto mode or a local manual alias.",
    inputSchema: {
      type: "object",
      properties: {
        mode: {
          type: "string",
          enum: ["auto", "manual"],
          default: "auto",
          description: "Use auto to follow system language, or manual to use a local custom name.",
        },
        display_name: {
          type: "string",
          maxLength: 64,
          description: "Manual display name, required when mode is manual.",
        },
        short_description: {
          type: "string",
          maxLength: 128,
          description: "Optional manual short description.",
        },
        clear_manual: {
          type: "boolean",
          default: false,
          description: "When switching to auto, clear the saved manual name.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "apply_display_profile",
    description: "Write the active display profile into the local plugin manifest. Codex must reload the plugin to show it.",
    inputSchema: {
      type: "object",
      properties: {
        display_name: {
          type: "string",
          maxLength: 64,
          description: "Optional display name override. Defaults to the active display profile.",
        },
        short_description: {
          type: "string",
          maxLength: 128,
          description: "Optional short-description override. Defaults to the active display profile.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "list_adapters",
    description: "List available compatibility adapters for local screen, window, audio, and video-audio access.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
  },
  {
    name: "list_audio_devices",
    description: "Optionally probe local audio capture devices for microphone or best-effort Windows loopback recording.",
    inputSchema: {
      type: "object",
      properties: {
        probe: {
          type: "boolean",
          default: true,
          description: "When true, import the optional audio adapter and query devices. Requires audio_capture to be active.",
        },
        feature_flags: imageOutputProperties.feature_flags,
      },
      additionalProperties: false,
    },
  },
  {
    name: "record_audio",
    description: "Record a short local WAV clip from a microphone or best-effort system loopback source.",
    inputSchema: {
      type: "object",
      properties: {
        source: {
          type: "string",
          enum: ["microphone", "system_loopback", "system", "speaker", "output"],
          default: "microphone",
          description: "Audio source. System loopback is best-effort and depends on Windows WASAPI support.",
        },
        duration_seconds: {
          type: "number",
          minimum: 0.1,
          default: 5,
          description: "Recording duration. Bounds are controlled by runtime limits.",
        },
        sample_rate: {
          type: "integer",
          default: 44100,
          description: "Sample rate in Hz. Bounds are controlled by runtime limits.",
        },
        channels: {
          type: "integer",
          default: 1,
          description: "Number of channels. Bounds are controlled by runtime limits.",
        },
        device: {
          description: "Optional sounddevice device index or name.",
        },
        loopback: {
          type: "boolean",
          default: false,
          description: "Force WASAPI loopback behavior for output/system sound capture.",
        },
        ...audioCommonProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "analyze_audio",
    description: "Analyze a local 16-bit PCM WAV file for duration, RMS, peak, silence, and clipping.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Local WAV path to analyze.",
        },
        silence_threshold: {
          type: "number",
          default: 0.01,
          description: "Normalized amplitude threshold used for silence detection.",
        },
        feature_flags: imageOutputProperties.feature_flags,
      },
      required: ["path"],
      additionalProperties: false,
    },
  },
  {
    name: "extract_audio_track",
    description: "Extract a WAV audio track from a local video file through optional FFmpeg.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Local video file path.",
        },
        input_path: {
          type: "string",
          description: "Alias for path.",
        },
        start_seconds: {
          type: "number",
          minimum: 0,
          description: "Optional start offset.",
        },
        duration_seconds: {
          type: "number",
          minimum: 0.1,
          description: "Optional extracted duration. Bounds are controlled by runtime limits.",
        },
        sample_rate: {
          type: "integer",
          default: 44100,
        },
        channels: {
          type: "integer",
          default: 1,
        },
        timeout_seconds: {
          type: "integer",
          default: 120,
        },
        ...audioCommonProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "list_displays",
    description: "List connected displays and their capture coordinates.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
  },
  {
    name: "list_windows",
    description: "List visible Windows application windows with HWND, title, process, and bounds.",
    inputSchema: {
      type: "object",
      properties: {
        title_contains: windowTargetProperties.title_contains,
        title_contains_any: windowTargetProperties.title_contains_any,
        process_name: windowTargetProperties.process_name,
        process_names: windowTargetProperties.process_names,
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 200,
          default: 50,
          description: "Maximum number of windows to return.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "capture_screen",
    description: "Capture a full display or the full virtual desktop to a local image file.",
    inputSchema: {
      type: "object",
      properties: {
        display_index: {
          type: "integer",
          default: 1,
          description: "Display index. Use 0 for the full virtual desktop; 1+ for individual displays.",
        },
        adapter: {
          type: "string",
          enum: ["auto", "python-mss"],
          default: "auto",
          description: "Capture adapter. Use auto unless a specific backend is needed.",
        },
        ...imageOutputProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "capture_region",
    description: "Capture a rectangular region to a local image file.",
    inputSchema: {
      type: "object",
      properties: {
        display_index: {
          type: "integer",
          default: 1,
          description: "Display index used when relative_to_display is true.",
        },
        adapter: {
          type: "string",
          enum: ["auto", "python-mss"],
          default: "auto",
          description: "Capture adapter. Use auto unless a specific backend is needed.",
        },
        left: {
          type: "integer",
          description: "Region left coordinate.",
        },
        top: {
          type: "integer",
          description: "Region top coordinate.",
        },
        width: {
          type: "integer",
          minimum: 1,
          description: "Region width.",
        },
        height: {
          type: "integer",
          minimum: 1,
          description: "Region height.",
        },
        relative_to_display: {
          type: "boolean",
          default: true,
          description: "When true, left/top are relative to display_index.",
        },
        ...imageOutputProperties,
      },
      required: ["left", "top", "width", "height"],
      additionalProperties: false,
    },
  },
  {
    name: "capture_window",
    description: "Capture a specified program window by HWND, title, or process name. Quiet-preferred by default: the adapter does not activate or raise the window, and visible-screen fallback output returns a decision warning before saving.",
    inputSchema: {
      type: "object",
      properties: {
        ...windowTargetProperties,
        ...imageOutputProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "prepare_webpage_capture",
    description: "Prepare a local envelope for full-page, viewport, element, or nested scroll-container webpage capture without launching a browser.",
    inputSchema: {
      type: "object",
      properties: webpageCaptureProperties,
      required: ["url"],
      additionalProperties: false,
    },
  },
  {
    name: "capture_webpage",
    description: "Capture a rendered webpage to a local image using the optional Playwright adapter. Supports full_page, viewport, element, and scroll_container nested panel screenshots beyond the visible viewport.",
    inputSchema: {
      type: "object",
      properties: webpageCaptureProperties,
      required: ["url"],
      additionalProperties: false,
    },
  },
  {
    name: "analyze_image",
    description: "Analyze a local image file and recommend context and preprocessing mode without adding OCR dependencies.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Local image path to analyze.",
        },
      },
      required: ["path"],
      additionalProperties: false,
    },
  },
  {
    name: "preprocess_image",
    description: "Create a locally preprocessed copy of an existing image using text, UI, photo, or auto presets.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Local image path to preprocess.",
        },
        ...imageOutputProperties,
      },
      required: ["path"],
      additionalProperties: false,
    },
  },
  {
    name: "watch_screen",
    description: "Run a bounded local change detector that saves screenshots when a display, region, or matching window changes.",
    inputSchema: {
      type: "object",
      properties: {
        display_index: {
          type: "integer",
          default: 1,
          description: "Display index for screen/region watching. Use 0 for virtual desktop.",
        },
        adapter: {
          type: "string",
          enum: ["auto", "python-mss"],
          default: "auto",
        },
        left: {
          type: "integer",
          description: "Optional region left coordinate.",
        },
        top: {
          type: "integer",
          description: "Optional region top coordinate.",
        },
        width: {
          type: "integer",
          minimum: 1,
          description: "Optional region width.",
        },
        height: {
          type: "integer",
          minimum: 1,
          description: "Optional region height.",
        },
        relative_to_display: {
          type: "boolean",
          default: true,
          description: "When true, left/top are relative to display_index.",
        },
        region: {
          type: "object",
          properties: {
            left: { type: "integer" },
            top: { type: "integer" },
            width: { type: "integer", minimum: 1 },
            height: { type: "integer", minimum: 1 },
            relative_to_display: { type: "boolean", default: true },
          },
          additionalProperties: false,
          description: "Optional region object. Direct left/top/width/height are also accepted.",
        },
        ...windowTargetProperties,
        duration_seconds: {
          type: "number",
          minimum: 0.1,
          default: 3,
          description: "Bounded watch duration in seconds. Default runtime limits cap this, but set_runtime_limits can change or remove that cap.",
        },
        interval_seconds: {
          type: "number",
          default: 0.5,
          description: "Polling interval between samples. Bounds are controlled by runtime limits.",
        },
        change_threshold: {
          type: "number",
          minimum: 0,
          default: 8,
          description: "Average pixel-difference threshold required before saving a changed frame.",
        },
        max_captures: {
          type: "integer",
          minimum: 1,
          default: 10,
          description: "Maximum captures saved during this bounded watch. Bounds are controlled by runtime limits.",
        },
        burst_frames: {
          type: "integer",
          minimum: 1,
          default: 1,
          description: "Number of consecutive frames to save after a detected change. Bounds are controlled by runtime limits.",
        },
        save_initial: {
          type: "boolean",
          default: false,
          description: "Save the first sampled frame before waiting for a change.",
        },
        ...imageOutputProperties,
      },
      additionalProperties: false,
    },
  },
  {
    name: "clear_cache",
    description: "Delete Screen Guardian-owned files from the default or configured local cache folders only.",
    inputSchema: {
      type: "object",
      properties: {
        output_dir: {
          type: "string",
          description: "Optional configured local cache or storage-route folder. Arbitrary directories are rejected.",
        },
        all: {
          type: "boolean",
          default: false,
          description: "Delete all Screen Guardian captures in the cache folder.",
        },
        older_than_days: {
          type: "number",
          minimum: 0,
          description: "Delete captures older than this many days.",
        },
      },
      additionalProperties: false,
    },
  },
];

const CORE_TOOL_NAMES = new Set([
  "guardian_check",
  "guardian_radar",
  "guardian_extract_page_facts",
  "guardian_capture_targets",
  "guardian_sniff_context",
  "guardian_perceive",
  "guardian_survey_windows",
  "check_dependencies",
  "list_adapters",
  "list_displays",
  "list_windows",
  "list_capture_routes",
  "capture_screen",
  "capture_region",
  "capture_window",
  "watch_screen",
  "clear_cache",
]);

const ADVANCED_TOOL_NAMES = new Set([
  "guardian_prepare_workflow",
  "guardian_list_commands",
  "guardian_run_command",
  "set_cache_path",
  "set_storage_routes",
  "set_runtime_limits",
  "set_feature_flags",
  "get_runtime_settings",
  "get_display_profile",
  "set_display_name",
  "apply_display_profile",
  "analyze_image",
  "preprocess_image",
  "prepare_webpage_capture",
  "capture_webpage",
  "list_audio_devices",
  "record_audio",
  "analyze_audio",
  "extract_audio_track",
  "list_extension_routes",
  "set_extension_route",
  "prepare_model_request",
  "prepare_data_layer_request",
  "list_decision_policies",
  "set_decision_policy",
  "prepare_decision_request",
  "list_monitor_profiles",
  "set_monitor_profile",
  "prepare_monitor_tick",
  "prepare_capture_chain",
]);

const LAB_TOOL_NAMES = new Set([
  "guardian_prepare_exec",
  "guardian_run_exec",
]);

function currentToolSurface() {
  const raw = String(process.env.SCREEN_GUARDIAN_TOOL_SURFACE || "core").trim().toLowerCase();
  if (["full", "all", "lab", "dev"].includes(raw)) {
    return "full";
  }
  if (["advanced", "expert"].includes(raw)) {
    return "advanced";
  }
  return "core";
}

function toolVisible(name) {
  const surface = currentToolSurface();
  if (CORE_TOOL_NAMES.has(name)) {
    return true;
  }
  if (surface === "advanced" && ADVANCED_TOOL_NAMES.has(name)) {
    return true;
  }
  if (surface === "full" && (ADVANCED_TOOL_NAMES.has(name) || LAB_TOOL_NAMES.has(name))) {
    return true;
  }
  return false;
}

function visibleTools() {
  return tools.filter((tool) => toolVisible(tool.name));
}

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function sendResult(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function sendError(id, code, message) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

function addPythonCandidate(candidates, command, prefixArgs, source) {
  if (!command) {
    return;
  }
  candidates.push({
    command,
    prefixArgs: prefixArgs || [],
    source,
  });
}

function pythonCandidates() {
  const candidates = [];
  for (const [source, value] of [
    ["SCREEN_GUARDIAN_PYTHON", process.env.SCREEN_GUARDIAN_PYTHON],
    ["PYTHON", process.env.PYTHON],
  ]) {
    if (value) {
      addPythonCandidate(candidates, value, [], source);
    }
  }

  const versionDirs = ["Python313", "Python312", "Python311", "Python310"];
  for (const base of [
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, "Programs", "Python"),
    process.env.USERPROFILE && path.join(process.env.USERPROFILE, "AppData", "Local", "Programs", "Python"),
    process.env.ProgramFiles && path.join(process.env.ProgramFiles, "Python"),
    process.env["ProgramFiles(x86)"] && path.join(process.env["ProgramFiles(x86)"], "Python"),
  ]) {
    if (!base) {
      continue;
    }
    for (const versionDir of versionDirs) {
      addPythonCandidate(candidates, path.join(base, versionDir, "python.exe"), [], "common-install-path");
    }
  }

  addPythonCandidate(candidates, "py", ["-3.13"], "windows-launcher");
  addPythonCandidate(candidates, "py", ["-3.12"], "windows-launcher");
  addPythonCandidate(candidates, "py", ["-3.11"], "windows-launcher");
  addPythonCandidate(candidates, "py", ["-3"], "windows-launcher");
  addPythonCandidate(candidates, "python", [], "PATH");
  addPythonCandidate(candidates, "python3", [], "PATH");

  const seen = new Set();
  return candidates
    .map((candidate) => {
      const key = `${candidate.command}\0${candidate.prefixArgs.join(" ")}`;
      if (seen.has(key)) {
        return null;
      }
      seen.add(key);
      const isExplicitPath = candidate.command.includes(path.sep) || candidate.command.endsWith(".exe");
      if (isExplicitPath && !fs.existsSync(candidate.command)) {
        return {
          ...candidate,
          skipped: true,
          skipReason: "path does not exist",
        };
      }
      return candidate;
    })
    .filter(Boolean);
}

function addPathCandidate(candidates, filePath, source) {
  if (!filePath) {
    return;
  }
  candidates.push({ path: filePath, source });
}

function uniquePathCandidates(candidates) {
  const seen = new Set();
  return candidates
    .map((candidate) => {
      const resolved = path.resolve(candidate.path);
      const key = resolved.toLowerCase();
      if (seen.has(key)) {
        return null;
      }
      seen.add(key);
      return {
        ...candidate,
        path: resolved,
        available: fs.existsSync(resolved),
      };
    })
    .filter(Boolean);
}

function runningFromPluginCache() {
  const normalized = ROOT.toLowerCase();
  const cacheMarker = `${path.sep}.codex${path.sep}plugins${path.sep}cache${path.sep}`.toLowerCase();
  return normalized.includes(cacheMarker);
}

function readPluginManifest(root) {
  if (!root) {
    return {};
  }
  try {
    const manifestPath = path.join(root, ".codex-plugin", "plugin.json");
    return JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  } catch (_err) {
    return {};
  }
}

function pluginRootForRuntimeFile(filePath) {
  if (!filePath) {
    return "";
  }
  return path.resolve(path.dirname(filePath), "..");
}

function fileSha256(filePath) {
  try {
    const hash = crypto.createHash("sha256");
    hash.update(fs.readFileSync(filePath));
    return hash.digest("hex");
  } catch (_err) {
    return "";
  }
}

function allowUntrustedRuntime() {
  const value = String(process.env.SCREEN_GUARDIAN_ALLOW_UNTRUSTED_RUNTIME || "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

function annotateRuntimeFileCandidate(candidate) {
  const activeRoot = pluginRootForRuntimeFile(candidate.path);
  const manifest = readPluginManifest(activeRoot);
  const trustedRoot = manifest.name === SERVER_NAME;
  const allowed = trustedRoot || allowUntrustedRuntime() || !candidate.available;
  return {
    ...candidate,
    activeRoot,
    activeManifestVersion: manifest.version || "",
    trustedRoot,
    sha256: candidate.available ? fileSha256(candidate.path) : "",
    skipped: candidate.skipped || !allowed,
    skipReason: candidate.skipReason || (!allowed ? "runtime file is outside a trusted Screen Guardian plugin root" : ""),
  };
}

function runtimeConsistency(candidate) {
  const activeRoot = candidate.activeRoot || pluginRootForRuntimeFile(candidate.scriptPath || candidate.command);
  const serverManifest = readPluginManifest(ROOT);
  const activeManifest = readPluginManifest(activeRoot);
  const serverVersion = serverManifest.version || "";
  const activeVersion = activeManifest.version || candidate.activeManifestVersion || "";
  const rootsMatch = !!activeRoot && path.resolve(activeRoot).toLowerCase() === path.resolve(ROOT).toLowerCase();
  const versionsMatch = !!serverVersion && !!activeVersion && serverVersion === activeVersion;
  return {
    server_root: ROOT,
    active_script_root: activeRoot || "",
    server_manifest_version: serverVersion,
    active_manifest_version: activeVersion,
    roots_match: rootsMatch,
    versions_match: versionsMatch,
    mixed_runtime: !!activeRoot && (!rootsMatch || !versionsMatch),
    trusted_root: candidate.trustedRoot !== false,
    runtime_file_sha256: candidate.sha256 || "",
  };
}

function implicitSourceFallbackAllowed() {
  const value = String(process.env.SCREEN_GUARDIAN_ALLOW_SOURCE_FALLBACK || "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || !runningFromPluginCache();
}

function sourcePluginRoots() {
  const roots = [];
  addPathCandidate(roots, process.env.SCREEN_GUARDIAN_PLUGIN_ROOT, "SCREEN_GUARDIAN_PLUGIN_ROOT");
  if (implicitSourceFallbackAllowed()) {
    addPathCandidate(roots, path.join(os.homedir(), "plugins", "screen-guardian"), "home-source");
    addPathCandidate(roots, path.join(process.env.USERPROFILE || "", "plugins", "screen-guardian"), "userprofile-source");
  }
  return uniquePathCandidates(roots).filter((candidate) => candidate.available && readPluginManifest(candidate.path).name === SERVER_NAME);
}

function cacheSiblingRoots() {
  const parent = path.dirname(ROOT);
  if (!fs.existsSync(parent)) {
    return [];
  }
  try {
    return fs
      .readdirSync(parent, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => {
        const fullPath = path.join(parent, entry.name);
        let mtimeMs = 0;
        try {
          mtimeMs = fs.statSync(fullPath).mtimeMs;
        } catch (_err) {
          mtimeMs = 0;
        }
        return { path: fullPath, source: "cache-sibling", mtimeMs };
      })
      .filter((candidate) => readPluginManifest(candidate.path).name === SERVER_NAME)
      .sort((a, b) => b.mtimeMs - a.mtimeMs || b.path.localeCompare(a.path));
  } catch (_err) {
    return [];
  }
}

function captureScriptCandidates() {
  const candidates = [];
  addPathCandidate(candidates, process.env.SCREEN_GUARDIAN_CAPTURE_SCRIPT, "SCREEN_GUARDIAN_CAPTURE_SCRIPT");
  addPathCandidate(candidates, path.join(ROOT, "scripts", CAPTURE_SCRIPT_NAME), "current-plugin-root");
  for (const candidate of sourcePluginRoots()) {
    addPathCandidate(candidates, path.join(candidate.path, "scripts", CAPTURE_SCRIPT_NAME), candidate.source);
  }
  for (const candidate of cacheSiblingRoots()) {
    addPathCandidate(candidates, path.join(candidate.path, "scripts", CAPTURE_SCRIPT_NAME), candidate.source);
  }
  return uniquePathCandidates(candidates).map(annotateRuntimeFileCandidate);
}

function helperExeCandidates() {
  const candidates = [];
  addPathCandidate(candidates, process.env.SCREEN_GUARDIAN_HELPER_EXE, "SCREEN_GUARDIAN_HELPER_EXE");
  addPathCandidate(candidates, path.join(ROOT, "bin", HELPER_EXE_NAME), "current-plugin-root");
  for (const candidate of sourcePluginRoots()) {
    addPathCandidate(candidates, path.join(candidate.path, "bin", HELPER_EXE_NAME), candidate.source);
  }
  for (const candidate of cacheSiblingRoots()) {
    addPathCandidate(candidates, path.join(candidate.path, "bin", HELPER_EXE_NAME), candidate.source);
  }
  return uniquePathCandidates(candidates)
    .map(annotateRuntimeFileCandidate)
    .filter((candidate) => candidate.available || candidate.source === "SCREEN_GUARDIAN_HELPER_EXE");
}

function runtimeCandidates() {
  const candidates = [];
  const helperCandidates = helperExeCandidates();
  const scriptCandidates = captureScriptCandidates();

  for (const helper of helperCandidates) {
    candidates.push({
      kind: "helper",
      command: helper.path,
      prefixArgs: [],
      source: helper.source,
      skipped: helper.skipped || !helper.available,
      skipReason: helper.skipReason || "helper executable does not exist",
      activeRoot: helper.activeRoot,
      activeManifestVersion: helper.activeManifestVersion,
      trustedRoot: helper.trustedRoot,
      sha256: helper.sha256,
    });
  }

  for (const script of scriptCandidates) {
    if (!script.available) {
      candidates.push({
        kind: "script",
        command: script.path,
        prefixArgs: [],
        source: script.source,
        skipped: true,
        skipReason: script.skipReason || "capture script does not exist",
        scriptPath: script.path,
        scriptSource: script.source,
        activeRoot: script.activeRoot,
        activeManifestVersion: script.activeManifestVersion,
        trustedRoot: script.trustedRoot,
        sha256: script.sha256,
      });
      continue;
    }
    for (const python of pythonCandidates()) {
      candidates.push({
        kind: "python",
        command: python.command,
        prefixArgs: python.prefixArgs,
        source: python.source,
        skipped: python.skipped || script.skipped,
        skipReason: python.skipReason || script.skipReason,
        scriptPath: script.path,
        scriptSource: script.source,
        activeRoot: script.activeRoot,
        activeManifestVersion: script.activeManifestVersion,
        trustedRoot: script.trustedRoot,
        sha256: script.sha256,
      });
    }
  }

  return candidates;
}

function summarizeAttempt(candidate, status, extra) {
  const consistency = runtimeConsistency(candidate);
  return {
    kind: candidate.kind || "python",
    command: candidate.command,
    prefix_args: candidate.prefixArgs,
    source: candidate.source,
    script_path: candidate.scriptPath || "",
    script_source: candidate.scriptSource || "",
    active_script_root: consistency.active_script_root,
    active_manifest_version: consistency.active_manifest_version,
    server_manifest_version: consistency.server_manifest_version,
    mixed_runtime: consistency.mixed_runtime,
    trusted_root: consistency.trusted_root,
    runtime_file_sha256: consistency.runtime_file_sha256,
    status,
    ...(extra || {}),
  };
}

function safeTextTail(value, maxLength = 2000) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(text.length - maxLength);
}

function runtimeInfo(candidate, attempts) {
  const consistency = runtimeConsistency(candidate);
  return {
    kind: candidate.kind || "python",
    command: candidate.command,
    prefix_args: candidate.prefixArgs,
    source: candidate.source,
    script_path: candidate.scriptPath || "",
    script_source: candidate.scriptSource || "",
    server_root: ROOT,
    active_script_root: consistency.active_script_root,
    server_manifest_version: consistency.server_manifest_version,
    active_manifest_version: consistency.active_manifest_version,
    roots_match: consistency.roots_match,
    versions_match: consistency.versions_match,
    mixed_runtime: consistency.mixed_runtime,
    trusted_root: consistency.trusted_root,
    runtime_file_sha256: consistency.runtime_file_sha256,
    running_from_plugin_cache: runningFromPluginCache(),
    skipped_or_failed_candidates: attempts,
  };
}

function boundedNumber(value, fallback, minValue, maxValue) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, parsed));
}

function childTimeoutMs(action, args) {
  const envTimeout = process.env.SCREEN_GUARDIAN_MCP_CHILD_TIMEOUT_MS;
  if (envTimeout) {
    return boundedNumber(envTimeout, 45000, 1000, 600000);
  }
  const data = args || {};
  if (action === "watch_screen") {
    return boundedNumber((Number(data.duration_seconds || 3) * 1000) + 10000, 20000, 5000, 90000);
  }
  if (action === "record_audio") {
    return boundedNumber((Number(data.duration_seconds || 1) * 1000) + 15000, 30000, 5000, 180000);
  }
  if (action === "capture_webpage" || action === "prepare_webpage_capture") {
    return boundedNumber(Number(data.timeout_ms || 15000) + 15000, 45000, 5000, 120000);
  }
  if (action === "guardian_run_exec" || action === "guardian_prepare_exec") {
    return boundedNumber((Number(data.timeout_seconds || 30) * 1000) + 10000, 45000, 5000, 180000);
  }
  if (action === "extract_audio_track") {
    return 180000;
  }
  return 45000;
}

function streamLimitBytes(kind) {
  const envName = kind === "stdout" ? "SCREEN_GUARDIAN_MCP_STDOUT_BYTES_MAX" : "SCREEN_GUARDIAN_MCP_STDERR_BYTES_MAX";
  const fallback = kind === "stdout" ? MAX_STDOUT_BYTES : MAX_STDERR_BYTES;
  return boundedNumber(process.env[envName], fallback, 65536, 16 * 1024 * 1024);
}

function killProcessTree(child) {
  if (!child || !child.pid) {
    return;
  }
  if (process.platform === "win32") {
    try {
      spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true });
      return;
    } catch (_err) {
      // Fall back below.
    }
  }
  try {
    child.kill("SIGKILL");
  } catch (_err) {
    try {
      child.kill();
    } catch (_err2) {
      // Best effort only.
    }
  }
}

function parseRuntimeJson(stdout) {
  const trimmed = String(stdout || "").trim();
  if (!trimmed) {
    throw new Error("stdout is empty");
  }
  try {
    return JSON.parse(trimmed);
  } catch (_err) {
    // Continue with framed fallbacks.
  }
  const lines = trimmed.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (line.startsWith("{") && line.endsWith("}")) {
      try {
        return JSON.parse(line);
      } catch (_err) {
        // Try earlier lines.
      }
    }
  }
  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return JSON.parse(trimmed.slice(start, end + 1));
  }
  throw new Error("stdout did not contain a JSON object");
}

function runPython(action, args) {
  const request = JSON.stringify({ action, args: args || {} });
  const candidates = runtimeCandidates();
  const timeoutMs = childTimeoutMs(action, args || {});

  return new Promise((resolve) => {
    let index = 0;
    const attempts = [];

    const failAll = (detail) => {
      resolve({
        ok: false,
        error: "Unable to start Python.",
        detail: detail || "No Python executable candidate succeeded.",
        attempts,
        runtime_strategy: {
          preferred_helper_env: "SCREEN_GUARDIAN_HELPER_EXE",
          preferred_env: "SCREEN_GUARDIAN_PYTHON",
          preferred_script_env: "SCREEN_GUARDIAN_CAPTURE_SCRIPT",
          plugin_root_env: "SCREEN_GUARDIAN_PLUGIN_ROOT",
          source_fallback_env: "SCREEN_GUARDIAN_ALLOW_SOURCE_FALLBACK",
          mcp_child_timeout_env: "SCREEN_GUARDIAN_MCP_CHILD_TIMEOUT_MS",
          stdout_limit_env: "SCREEN_GUARDIAN_MCP_STDOUT_BYTES_MAX",
          stderr_limit_env: "SCREEN_GUARDIAN_MCP_STDERR_BYTES_MAX",
          untrusted_runtime_env: "SCREEN_GUARDIAN_ALLOW_UNTRUSTED_RUNTIME",
          server_root: ROOT,
          server_manifest_version: readPluginManifest(ROOT).version || "",
          running_from_plugin_cache: runningFromPluginCache(),
          fallback_order: [
            "helper executable",
            "capture script env",
            "current plugin root",
            "explicit plugin root env",
            "newer sibling cache roots",
            "source folder only outside cache or when explicitly allowed",
            "PYTHON",
            "common install paths",
            "py launcher",
            "python",
            "python3",
          ],
        },
      });
    };

    const failTimeout = (candidate, stdout, stderr, sawOutput) => {
      resolve({
        ok: false,
        error: "Screen Guardian runtime timed out.",
        detail: `Runtime child exceeded ${timeoutMs} ms for action '${action}'.`,
        action,
        timeout_ms: timeoutMs,
        python_runtime: runtimeInfo(candidate, attempts),
        stdout_tail: safeTextTail(stdout),
        stderr_tail: safeTextTail(stderr),
        saw_output: sawOutput,
      });
    };

    const tryNext = () => {
      if (index >= candidates.length) {
        failAll("All Python candidates failed or were skipped.");
        return false;
      }

      const candidate = candidates[index++];
      if (candidate.skipped) {
        attempts.push(summarizeAttempt(candidate, "skipped", { detail: candidate.skipReason }));
        tryNext();
        return;
      }
      const consistency = runtimeConsistency(candidate);
      if (consistency.mixed_runtime && MIXED_ROOT_BLOCKED_ACTIONS.has(action)) {
        attempts.push(
          summarizeAttempt(candidate, "skipped", {
            detail: "action is blocked for mixed MCP root/runtime script roots",
            blocked_action: action,
            runtime_consistency: consistency,
          })
        );
        tryNext();
        return;
      }

      const childArgs = candidate.kind === "helper" ? [request] : [...candidate.prefixArgs, candidate.scriptPath, request];
      const child = spawn(candidate.command, childArgs, {
        cwd: ROOT,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        windowsHide: true,
      });

      let stdout = "";
      let stderr = "";
      let stdoutBytes = 0;
      let stderrBytes = 0;
      const stdoutLimit = streamLimitBytes("stdout");
      const stderrLimit = streamLimitBytes("stderr");
      let sawOutput = false;
      let finished = false;
      const timer = setTimeout(() => {
        if (finished) {
          return;
        }
        finished = true;
        attempts.push(
          summarizeAttempt(candidate, "timeout", {
            timeout_ms: timeoutMs,
            stdout: safeTextTail(stdout),
            stderr: safeTextTail(stderr),
            saw_output: sawOutput,
          })
        );
        killProcessTree(child);
        failTimeout(candidate, stdout, stderr, sawOutput);
      }, timeoutMs);

      child.stdout.on("data", (chunk) => {
        sawOutput = true;
        stdoutBytes += Buffer.byteLength(chunk);
        stdout += chunk.toString();
        if (!finished && stdoutBytes > stdoutLimit) {
          finished = true;
          clearTimeout(timer);
          attempts.push(
            summarizeAttempt(candidate, "output-limit", {
              stream: "stdout",
              limit_bytes: stdoutLimit,
              stdout: safeTextTail(stdout),
              stderr: safeTextTail(stderr),
            })
          );
          killProcessTree(child);
          tryNext();
        }
      });
      child.stderr.on("data", (chunk) => {
        sawOutput = true;
        stderrBytes += Buffer.byteLength(chunk);
        stderr += chunk.toString();
        if (!finished && stderrBytes > stderrLimit) {
          finished = true;
          clearTimeout(timer);
          attempts.push(
            summarizeAttempt(candidate, "output-limit", {
              stream: "stderr",
              limit_bytes: stderrLimit,
              stdout: safeTextTail(stdout),
              stderr: safeTextTail(stderr),
            })
          );
          killProcessTree(child);
          tryNext();
        }
      });
      child.on("error", (err) => {
        if (finished) {
          return;
        }
        finished = true;
        clearTimeout(timer);
        attempts.push(summarizeAttempt(candidate, "error", { detail: err.message, saw_output: sawOutput }));
        tryNext();
      });
      child.on("close", (code) => {
        if (finished) {
          return;
        }
        finished = true;
        clearTimeout(timer);
        if (!stdout && code !== 0) {
          attempts.push(
            summarizeAttempt(candidate, "failed", {
              exit_code: code,
              stderr: safeTextTail(stderr),
            })
          );
          tryNext();
          return;
        }

        try {
          const parsed = parseRuntimeJson(stdout);
          if (stderr.trim()) {
            parsed.stderr = safeTextTail(stderr, 12000);
          }
          parsed.python_runtime = runtimeInfo(candidate, attempts);
          parsed.runtime_consistency = parsed.python_runtime;
          resolve(parsed);
        } catch (err) {
          attempts.push(
            summarizeAttempt(candidate, "invalid-json", {
              exit_code: code,
              stdout: safeTextTail(stdout),
              stderr: safeTextTail(stderr),
              detail: err.message,
            })
          );
          tryNext();
        }
      });
    };

    tryNext();
  });
}

async function callTool(name, args) {
  if (name === "guardian_check") {
    return runPython("guardian_check", args);
  }
  if (name === "guardian_radar") {
    return runPython("guardian_radar", args);
  }
  if (name === "guardian_extract_page_facts") {
    return runPython("guardian_extract_page_facts", args);
  }
  if (name === "guardian_capture_targets") {
    return runPython("guardian_capture_targets", args);
  }
  if (name === "guardian_sniff_context") {
    return runPython("guardian_sniff_context", args);
  }
  if (name === "guardian_perceive") {
    return runPython("guardian_perceive", args);
  }
  if (name === "guardian_survey_windows") {
    return runPython("guardian_survey_windows", args);
  }
  if (name === "guardian_prepare_workflow") {
    return runPython("guardian_prepare_workflow", args);
  }
  if (name === "guardian_list_commands") {
    return runPython("guardian_list_commands", args);
  }
  if (name === "guardian_run_command") {
    return runPython("guardian_run_command", args);
  }
  if (name === "guardian_prepare_exec") {
    return runPython("guardian_prepare_exec", args);
  }
  if (name === "guardian_run_exec") {
    return runPython("guardian_run_exec", args);
  }
  if (name === "list_capture_routes") {
    return runPython("list_capture_routes", args);
  }
  if (name === "prepare_capture_chain") {
    return runPython("prepare_capture_chain", args);
  }
  if (name === "check_dependencies") {
    return runPython("check", args);
  }
  if (name === "get_runtime_settings") {
    return runPython("get_runtime_settings", args);
  }
  if (name === "set_cache_path") {
    return runPython("set_cache_path", args);
  }
  if (name === "set_storage_routes") {
    return runPython("set_storage_routes", args);
  }
  if (name === "set_runtime_limits") {
    return runPython("set_runtime_limits", args);
  }
  if (name === "set_feature_flags") {
    return runPython("set_feature_flags", args);
  }
  if (name === "list_extension_routes") {
    return runPython("list_extension_routes", args);
  }
  if (name === "set_extension_route") {
    return runPython("set_extension_route", args);
  }
  if (name === "prepare_model_request") {
    return runPython("prepare_model_request", args);
  }
  if (name === "prepare_data_layer_request") {
    return runPython("prepare_data_layer_request", args);
  }
  if (name === "list_decision_policies") {
    return runPython("list_decision_policies", args);
  }
  if (name === "set_decision_policy") {
    return runPython("set_decision_policy", args);
  }
  if (name === "prepare_decision_request") {
    return runPython("prepare_decision_request", args);
  }
  if (name === "list_monitor_profiles") {
    return runPython("list_monitor_profiles", args);
  }
  if (name === "set_monitor_profile") {
    return runPython("set_monitor_profile", args);
  }
  if (name === "prepare_monitor_tick") {
    return runPython("prepare_monitor_tick", args);
  }
  if (name === "get_display_profile") {
    return runPython("get_display_profile", args);
  }
  if (name === "set_display_name") {
    return runPython("set_display_name", args);
  }
  if (name === "apply_display_profile") {
    return runPython("apply_display_profile", args);
  }
  if (name === "list_adapters") {
    return runPython("list_adapters", args);
  }
  if (name === "list_audio_devices") {
    return runPython("list_audio_devices", args);
  }
  if (name === "record_audio") {
    return runPython("record_audio", args);
  }
  if (name === "analyze_audio") {
    return runPython("analyze_audio", args);
  }
  if (name === "extract_audio_track") {
    return runPython("extract_audio_track", args);
  }
  if (name === "list_displays") {
    return runPython("list_displays", args);
  }
  if (name === "list_windows") {
    return runPython("list_windows", args);
  }
  if (name === "capture_screen") {
    return runPython("capture_screen", args);
  }
  if (name === "capture_region") {
    return runPython("capture_region", args);
  }
  if (name === "capture_window") {
    return runPython("capture_window", args);
  }
  if (name === "prepare_webpage_capture") {
    return runPython("prepare_webpage_capture", args);
  }
  if (name === "capture_webpage") {
    return runPython("capture_webpage", args);
  }
  if (name === "analyze_image") {
    return runPython("analyze_image", args);
  }
  if (name === "preprocess_image") {
    return runPython("preprocess_image", args);
  }
  if (name === "watch_screen") {
    return runPython("watch_screen", args);
  }
  if (name === "clear_cache") {
    return runPython("clear_cache", args);
  }
  return { ok: false, error: `Unknown tool: ${name}` };
}

async function handle(message) {
  const { id, method, params } = message;
  const isRequest = Object.prototype.hasOwnProperty.call(message, "id");

  try {
    if (method === "initialize") {
      if (isRequest) {
        sendResult(id, {
          protocolVersion: params?.protocolVersion || "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
        });
      }
      return;
    }

    if (method === "tools/list") {
      sendResult(id, {
        tools: visibleTools(),
        toolSurface: currentToolSurface(),
      });
      return;
    }

    if (method === "tools/call") {
      if (!toolVisible(params?.name)) {
        const result = {
          ok: false,
          error: `Tool '${params?.name}' is hidden on the current '${currentToolSurface()}' surface.`,
          tool_surface: currentToolSurface(),
          available_surfaces: {
            core: Array.from(CORE_TOOL_NAMES),
            advanced: Array.from(new Set([...CORE_TOOL_NAMES, ...ADVANCED_TOOL_NAMES])),
            full: Array.from(new Set([...CORE_TOOL_NAMES, ...ADVANCED_TOOL_NAMES, ...LAB_TOOL_NAMES])),
          },
          enable_hint: "Set SCREEN_GUARDIAN_TOOL_SURFACE=advanced or full before starting the MCP server to expose advanced/lab tools.",
        };
        sendResult(id, {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
          isError: true,
        });
        return;
      }
      const result = await callTool(params?.name, params?.arguments || {});
      sendResult(id, {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
        isError: !result.ok,
      });
      return;
    }

    if (method === "resources/list") {
      sendResult(id, { resources: [] });
      return;
    }

    if (method === "prompts/list") {
      sendResult(id, { prompts: [] });
      return;
    }

    if (!isRequest) {
      return;
    }

    sendError(id, -32601, `Unsupported method: ${method}`);
  } catch (err) {
    if (isRequest) {
      sendError(id, -32603, err.message || String(err));
    }
  }
}

let buffer = "";
let queue = Promise.resolve();

function enqueue(message) {
  queue = queue
    .then(() => handle(message))
    .catch((err) => {
      sendError(
        Object.prototype.hasOwnProperty.call(message, "id") ? message.id : null,
        -32603,
        err.message || String(err),
      );
    });
}

process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  let newlineIndex = buffer.indexOf("\n");
  while (newlineIndex >= 0) {
    const line = buffer.slice(0, newlineIndex).trim();
    buffer = buffer.slice(newlineIndex + 1);
    if (line) {
      try {
        enqueue(JSON.parse(line));
      } catch (err) {
        sendError(null, -32700, err.message || String(err));
      }
    }
    newlineIndex = buffer.indexOf("\n");
  }
});

process.stdin.on("end", () => {
  queue.finally(() => process.exit(0));
});
