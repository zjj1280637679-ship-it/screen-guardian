const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const SERVER_NAME = "screen-guardian";
const SERVER_VERSION = "0.1.9";
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
    description: "Optional per-call runtime limit overrides.",
    additionalProperties: true,
  },
  feature_flags: {
    type: "object",
    description: "Optional per-call feature flag overrides.",
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
    description: "Pick the first visible window whose title contains this text.",
  },
  title_contains_any: {
    type: "array",
    items: { type: "string" },
    description: "Pick the first visible window matching any title fragment.",
  },
  exact_title: {
    type: "string",
    description: "Pick the first visible window whose title exactly matches this string.",
  },
  process_name: {
    type: "string",
    description: "Pick the first visible window whose process name contains this text.",
  },
  process_names: {
    type: "array",
    items: { type: "string" },
    description: "Pick the first visible window matching any process name fragment.",
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
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "transcription", "custom"],
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
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "transcription", "custom"],
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
    description: "Write a local request envelope for an external judgment/OCR/narration model, including follow-up questions and model settings.",
    inputSchema: {
      type: "object",
      properties: {
        route_id: {
          type: "string",
          description: "Optional registered extension route id.",
        },
        role: {
          type: "string",
          enum: ["judgment", "ocr", "vision_summary", "video_summary", "transcription", "custom"],
          default: "vision_summary",
        },
        path: {
          type: "string",
          description: "Optional image/video/local file path for the model request.",
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
    description: "List available compatibility adapters for local screen and window access.",
    inputSchema: {
      type: "object",
      properties: {},
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
    description: "Delete Screen Guardian images from the local cache folder only.",
    inputSchema: {
      type: "object",
      properties: {
        output_dir: {
          type: "string",
          description: "Optional local cache folder. Defaults to the configured cache path or Pictures/ScreenGuardian.",
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

function pythonCandidates() {
  const candidates = [];
  for (const value of [process.env.PYTHON, process.env.npm_config_python]) {
    if (value) {
      candidates.push({ command: value, prefixArgs: [] });
    }
  }
  if (process.env.LOCALAPPDATA) {
    candidates.push({
      command: path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python312", "python.exe"),
      prefixArgs: [],
    });
    candidates.push({
      command: path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python311", "python.exe"),
      prefixArgs: [],
    });
  }
  candidates.push({
    command: path.join(process.env.USERPROFILE || "", "AppData", "Local", "Programs", "Python", "Python312", "python.exe"),
    prefixArgs: [],
  });
  candidates.push({ command: "py", prefixArgs: ["-3.12"] });
  candidates.push({ command: "python", prefixArgs: [] });
  candidates.push({ command: "python3", prefixArgs: [] });
  const seen = new Set();
  return candidates.filter((candidate) => {
    if (!candidate.command || seen.has(candidate.command)) {
      return false;
    }
    seen.add(candidate.command);
    return !candidate.command.endsWith(".exe") || fs.existsSync(candidate.command);
  });
}

function runPython(action, args) {
  const request = JSON.stringify({ action, args: args || {} });
  const candidates = pythonCandidates();

  return new Promise((resolve) => {
    let index = 0;

    const tryNext = (lastError) => {
      if (index >= candidates.length) {
        resolve({
          ok: false,
          error: "Unable to start Python.",
          detail: lastError || "No Python executable was found.",
        });
        return;
      }

      const candidate = candidates[index++];
      const childArgs = [...candidate.prefixArgs, CAPTURE_SCRIPT, request];
      const child = spawn(candidate.command, childArgs, {
        cwd: ROOT,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        windowsHide: true,
      });

      let stdout = "";
      let stderr = "";
      let started = false;

      child.stdout.on("data", (chunk) => {
        started = true;
        stdout += chunk.toString();
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });
      child.on("error", (err) => {
        if (!started) {
          tryNext(`${candidate.command}: ${err.message}`);
        } else {
          resolve({ ok: false, error: err.message });
        }
      });
      child.on("close", (code) => {
        if (!stdout && code !== 0) {
          tryNext(`${candidate.command}: exit ${code}${stderr.trim() ? `, ${stderr.trim()}` : ""}`);
          return;
        }

        try {
          const parsed = JSON.parse(stdout);
          if (stderr.trim()) {
            parsed.stderr = stderr.trim();
          }
          resolve(parsed);
        } catch (err) {
          resolve({
            ok: false,
            error: "Python capture script returned invalid JSON.",
            command: candidate.command,
            exit_code: code,
            stdout,
            stderr: stderr.trim(),
          });
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
