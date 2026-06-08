const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const SERVER_NAME = "screen-guardian";
const SERVER_VERSION = "0.1.11";
const ROOT = path.resolve(__dirname, "..");
const CAPTURE_SCRIPT = path.join(ROOT, "scripts", "screen_guardian_capture.py");

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

const tools = [
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
    description: "Capture a specified visible program window by HWND, title, or process name, even when best-effort non-topmost capture is available.",
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
    ["npm_config_python", process.env.npm_config_python],
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

function summarizeAttempt(candidate, status, extra) {
  return {
    command: candidate.command,
    prefix_args: candidate.prefixArgs,
    source: candidate.source,
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

function runPython(action, args) {
  const request = JSON.stringify({ action, args: args || {} });
  const candidates = pythonCandidates();

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
          preferred_env: "SCREEN_GUARDIAN_PYTHON",
          fallback_order: ["PYTHON", "npm_config_python", "common install paths", "py launcher", "python", "python3"],
        },
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

      const childArgs = [...candidate.prefixArgs, CAPTURE_SCRIPT, request];
      const child = spawn(candidate.command, childArgs, {
        cwd: ROOT,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        windowsHide: true,
      });

      let stdout = "";
      let stderr = "";
      let sawOutput = false;
      let finished = false;

      child.stdout.on("data", (chunk) => {
        sawOutput = true;
        stdout += chunk.toString();
      });
      child.stderr.on("data", (chunk) => {
        sawOutput = true;
        stderr += chunk.toString();
      });
      child.on("error", (err) => {
        if (finished) {
          return;
        }
        finished = true;
        attempts.push(summarizeAttempt(candidate, "error", { detail: err.message, saw_output: sawOutput }));
        tryNext();
      });
      child.on("close", (code) => {
        if (finished) {
          return;
        }
        finished = true;
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
          const parsed = JSON.parse(stdout);
          if (stderr.trim()) {
            parsed.stderr = stderr.trim();
          }
          parsed.python_runtime = {
            command: candidate.command,
            prefix_args: candidate.prefixArgs,
            source: candidate.source,
            skipped_or_failed_candidates: attempts,
          };
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
      sendResult(id, { tools });
      return;
    }

    if (method === "tools/call") {
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
