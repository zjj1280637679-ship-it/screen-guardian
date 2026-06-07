const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const SERVER_NAME = "screen-guardian";
const SERVER_VERSION = "0.1.0";
const ROOT = path.resolve(__dirname, "..");
const CAPTURE_SCRIPT = path.join(ROOT, "scripts", "screen_guardian_capture.py");

const tools = [
  {
    name: "check_dependencies",
    description: "Check local Python screenshot dependencies and default cache location.",
    inputSchema: {
      type: "object",
      properties: {
        output_dir: {
          type: "string",
          description: "Optional local folder for Screen Guardian captures.",
        },
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
    name: "capture_screen",
    description: "Capture a full display or the full virtual desktop to a local image file.",
    inputSchema: {
      type: "object",
      properties: {
        display_index: {
          type: "integer",
          description: "Display index. Use 0 for the full virtual desktop; 1+ for individual displays.",
          default: 1,
        },
        output_dir: {
          type: "string",
          description: "Optional local output folder.",
        },
        format: {
          type: "string",
          enum: ["png", "jpg"],
          default: "png",
        },
        scale: {
          type: "number",
          minimum: 0.01,
          maximum: 1,
          description: "Optional downscale factor between 0.01 and 1.",
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
          minimum: 1,
          maximum: 95,
          description: "JPEG quality when format is jpg.",
          default: 90,
        },
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
          description: "Display index used when relative_to_display is true.",
          default: 1,
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
        output_dir: {
          type: "string",
          description: "Optional local output folder.",
        },
        format: {
          type: "string",
          enum: ["png", "jpg"],
          default: "png",
        },
        scale: {
          type: "number",
          minimum: 0.01,
          maximum: 1,
        },
        max_width: {
          type: "integer",
          minimum: 1,
        },
        max_height: {
          type: "integer",
          minimum: 1,
        },
        quality: {
          type: "integer",
          minimum: 1,
          maximum: 95,
          default: 90,
        },
      },
      required: ["left", "top", "width", "height"],
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
          description: "Optional local cache folder. Defaults to Pictures/ScreenGuardian.",
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
  if (name === "list_displays") {
    return runPython("list_displays", args);
  }
  if (name === "capture_screen") {
    return runPython("capture_screen", args);
  }
  if (name === "capture_region") {
    return runPython("capture_region", args);
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
