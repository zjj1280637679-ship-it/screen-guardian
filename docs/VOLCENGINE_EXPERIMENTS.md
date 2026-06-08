# Volcengine Ark Experiments

Screen Guardian can prepare local model-request envelopes without uploading anything. The optional Ark runner in `scripts/volcengine_ark_runner.py` is the separate bridge for real Volcengine Ark experiments.

The bridge is intentionally outside the hot capture path:

- normal screenshots stay local-only
- no API key is stored in the repository
- no external request is made unless the user runs the runner
- request artifacts redact inline image, video, and audio bytes
- every real run writes a local response summary and JSONL ledger

## Current Account Rules To Track

From the current Ark console reward-plan page, authorized ByteDance models show these daily collection limits:

| Model family | Daily collection shown on page | Notes |
| --- | ---: | --- |
| Doubao vision models such as `Doubao-1.5-vision-pro`, `Doubao-1.5-vision-lite`, `Doubao-1.5-vision-pro-32k`, and `Doubao-Seed-1.6-vision` | `2,000,000 tokens` per model | Today value may show `-` until usage appears. |
| Most Doubao Seed text or multimodal models | `2,000,000 tokens` per model | Reward is based on authorized endpoint usage. |
| `Doubao-Seed-Code` | `5,000,000 tokens` | Higher daily collection limit on the current page. |
| Seedance video-generation models | `2,000,000 tokens` per model | Not the same thing as video understanding cost. |
| Seedream image-generation models | `20 images` per model | Image-generation quota is counted by generated image. |

Reward-plan resources are not the same as ordinary free inference quota or Agent Plan AFP. Treat them as separate ledgers:

- reward-plan daily collection: authorized endpoint usage returns a resource pack after the next day around 11:00, valid for 30 days
- free inference quota: model-specific free online inference balance, not documented as daily refreshing
- Agent Plan AFP: subscription quota with 5-hour, day, week, or month windows, depending on the field

## Run Pattern

1. Capture locally.
2. Prepare or choose the model route.
3. Dry-run the request.
4. Run one real call.
5. Compare local `usage` with the Ark usage-statistics page and resource-pack records.

## Environment

Use environment variables instead of files for secrets:

```powershell
$env:ARK_API_KEY = "your-ark-api-key"
$env:ARK_MODEL = "your-model-id"
```

Do not commit keys, response files, or account screenshots that include private billing or API-key data.

## Image Experiment

Capture a screen image and hold it as a file:

```powershell
$req = @{
  action = "capture_screen"
  args = @{
    source_label = "ark-image-test"
    context_policy = "hold_file"
    marked_file_only = $true
    max_width = 1280
    format = "jpg"
    jpeg_quality = 75
    tags = @("ark", "image", "baseline")
  }
} | ConvertTo-Json -Depth 10 -Compress
python .\scripts\screen_guardian_capture.py $req
```

Then dry-run and run the Ark request:

```powershell
$zhImagePrompt = [System.Text.RegularExpressions.Regex]::Unescape('\u8bf7\u7528\u4e2d\u6587\u7b80\u6d01\u63cf\u8ff0\u8fd9\u4e2a\u622a\u56fe\u4e2d\u5bf9\u6392\u67e5\u95ee\u9898\u6700\u91cd\u8981\u7684\u4fe1\u606f\u3002')

python .\scripts\volcengine_ark_runner.py `
  --dry-run `
  --path "C:\path\to\capture.jpg" `
  --media-kind image `
  --detail low `
  --thinking disabled `
  --max-tokens 300 `
  --prompt $zhImagePrompt

python .\scripts\volcengine_ark_runner.py `
  --path "C:\path\to\capture.jpg" `
  --media-kind image `
  --detail low `
  --thinking disabled `
  --max-tokens 300 `
  --prompt $zhImagePrompt
```

## Video Experiment

Prefer a hosted URL for larger videos. Start with low fps:

```powershell
$zhVideoPrompt = [System.Text.RegularExpressions.Regex]::Unescape('\u8bf7\u6309\u65f6\u95f4\u987a\u5e8f\u603b\u7ed3\u89c6\u9891\u91cc\u53d1\u751f\u4e86\u4ec0\u4e48\uff0c\u5e76\u6307\u51fa\u662f\u5426\u51fa\u73b0\u9519\u8bef\u754c\u9762\u3002')

python .\scripts\volcengine_ark_runner.py `
  --url "https://example.com/short-test.mp4" `
  --media-kind video `
  --fps 0.2 `
  --max-tokens 400 `
  --prompt $zhVideoPrompt
```

Use `fps=1` only after the low-fps baseline misses important motion. Reserve `fps=2` to `5` for fast-changing UI, games, or short test clips.

## Audio Experiment

If optional audio capture is installed and enabled, record a short WAV first. Then send the WAV to Ark:

```powershell
$zhAudioPrompt = [System.Text.RegularExpressions.Regex]::Unescape('\u8bf7\u5224\u65ad\u8fd9\u6bb5\u97f3\u9891\u662f\u5426\u6709\u660e\u663e\u5f02\u5e38\u58f0\u97f3\uff0c\u5e76\u7528\u4e2d\u6587\u7ed9\u51fa\u6392\u67e5\u5efa\u8bae\u3002')

python .\scripts\volcengine_ark_runner.py `
  --path "C:\path\to\clip.wav" `
  --media-kind audio `
  --max-tokens 300 `
  --prompt $zhAudioPrompt
```

For system sounds, first use local `analyze_audio` to check silence or clipping. Only send audio to a model when local diagnostics are not enough.

## Envelope Experiment

Registering a route is configuration only. It does not call Ark:

```powershell
$route = @{
  action = "set_extension_route"
  args = @{
    id = "ark-vision-low"
    role = "vision_summary"
    handoff_mode = "external_api"
    provider = "volcengine-ark"
    model = $env:ARK_MODEL
    endpoint = "https://ark.cn-beijing.volces.com/api/v3"
    api_key_env = "ARK_API_KEY"
    capabilities = @("image", "ocr-lite", "followups")
    settings = @{
      detail = "low"
      temperature = 0.2
      thinking = "disabled"
      max_tokens = 300
      language = "zh-CN"
    }
  }
} | ConvertTo-Json -Depth 10 -Compress
python .\scripts\screen_guardian_capture.py $route
```

Prepare a request envelope:

```powershell
$zhEnvelopePrompt = [System.Text.RegularExpressions.Regex]::Unescape('\u8bf7\u7528\u4e2d\u6587\u63cf\u8ff0\u622a\u56fe\uff0c\u5e76\u6307\u51fa\u4e0b\u4e00\u6b65\u5e94\u8be5\u770b\u54ea\u91cc\u3002')
$zhQuestion1 = [System.Text.RegularExpressions.Regex]::Unescape('\u662f\u5426\u5305\u542b\u9519\u8bef\u4fe1\u606f\uff1f')
$zhQuestion2 = [System.Text.RegularExpressions.Regex]::Unescape('\u662f\u5426\u503c\u5f97\u8f6c OCR\uff1f')

$request = @{
  action = "prepare_model_request"
  args = @{
    route_id = "ark-vision-low"
    role = "vision_summary"
    path = "C:\path\to\capture.jpg"
    prompt = $zhEnvelopePrompt
    questions = @($zhQuestion1, $zhQuestion2)
  }
} | ConvertTo-Json -Depth 10 -Compress
python .\scripts\screen_guardian_capture.py $request
```

Run the envelope:

```powershell
python .\scripts\volcengine_ark_runner.py --envelope "C:\path\to\model-request.json" --dry-run
python .\scripts\volcengine_ark_runner.py --envelope "C:\path\to\model-request.json"
```

## Ledger Fields

Each run writes:

- `*.request.redacted.json`
- `*.response.json`
- `*.summary.json`
- `volcengine-ark-ledger.jsonl`

Use the ledger for daily reconciliation:

- model
- media kind
- path or URL
- prompt hash and prompt length
- settings such as detail, fps, temperature, max tokens
- returned `usage`
- local artifact paths

Compare this with the Ark usage-statistics page by day, hour, endpoint, model, input tokens, output tokens, and total tokens.

## Safety Defaults

Use this order for cost control:

1. image: `detail=low`, `max_tokens=300`
2. video: `fps=0.2`, short clips, hosted URL
3. audio: short WAV, local silence/clipping analysis first
4. only raise detail, fps, or output tokens when a baseline misses useful evidence

The runner is a real external API bridge. It is not part of Screen Guardian's default local-only capture behavior.
