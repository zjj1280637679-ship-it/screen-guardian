# Screen Guardian 困难/边缘任务测试集

这份测试集用于检验 Screen Guardian 在复杂桌面环境里的真实能力边界。它不是证明“所有窗口都能后台捕获”，而是区分：

- 能直接后台图形获取
- 需要等待渲染后后台获取
- 只能走可见屏幕兜底
- 应该返回决策而不是保存误导图片
- 应该拒绝或降级

## 总验收原则

每个任务都要检查四件事：

1. 是否先给 AI 提供目标索引，而不是直接截图。
2. 是否没有把 UI 拉到前台、没有抢焦点、没有设置 topmost。
3. 当用户要求后台图形获取时，是否没有偷偷保存可见屏幕 bbox 兜底。
4. 失败时是否返回可行动的决策状态，而不是伪装成成功。

## 难度分级

| 等级 | 目标 | 通过条件 |
| --- | --- | --- |
| L0 | 工具契约 | `guardian_capture_targets` 出现在 core tools/list 中，`npm run validate` 通过。 |
| L1 | 普通目标索引 | 能列出显示器、窗口、显式 URL，且 `capture_performed=false`。 |
| L2 | 被遮挡窗口后台获取 | 对被其他窗口盖住的普通应用使用 `background_mode=strict`，保存窗口本体，元数据里 `visible_screen_fallback_used=false`。 |
| L3 | 失败不伪装 | 对 minimized/GPU/protected/低信息窗口使用 strict 时，如果直取不可用，返回 `background_capture_unavailable` 或 guard decision，不保存误导图。 |
| L4 | 混合路线判断 | AI 能在桌面、应用窗口、网页、嵌套滚动容器之间选择正确路线，并保留风险说明。 |

## 任务清单

| ID | 任务 | 设置 | 预期 |
| --- | --- | --- | --- |
| E01 | 预截图目标索引 | 调用 `guardian_capture_targets`，`limit=20`，带一个显式 URL。 | 返回 display/window/page targets；无截图、无导航、无上传。 |
| E02 | 被遮挡普通窗口 strict 捕获 | 让目标窗口被 Codex/Chrome 覆盖，按 HWND 调 `capture_window`。 | 保存图像；`capture_method=pillow-imagegrab-window`；无可见 bbox 兜底。 |
| E03 | 被遮挡窗口可见兜底拒绝 | 同一窗口用 strict，模拟或选择直取低信息目标。 | 不保存可见屏幕 bbox；返回 `background_capture_unavailable` 或 unrendered decision。 |
| E04 | 明确可见兜底 | 使用 `background_mode=visible_fallback`。 | 结果必须在元数据中标出 `visible_screen_fallback_used=true`，并带 occlusion/bbox identity 风险。 |
| E05 | bbox 身份不匹配 | 目标窗口被另一个窗口盖住，best-effort 触发 bbox fallback。 | 如果采样点不属于目标 HWND，返回 `bbox_identity_mismatch`，不默认保存。 |
| E06 | 多个同名窗口 | 打开多个 Chrome/记事本窗口，只传 title fragment。 | 返回 ambiguous/candidate windows，要求使用 HWND 或 exact title。 |
| E07 | 最小化窗口 | 最小化任务管理器或其他窗口后捕获。 | 返回 minimized/offscreen 风险；不把空白图当成功证据。 |
| E08 | 负坐标/多显示器 | 把窗口拖到虚拟桌面边缘或副屏。 | `visible_ratio`、rect、virtual_screen 正确；部分离屏要标 `partly_offscreen`。 |
| E09 | 慢渲染窗口 | 打开正在加载的网页或 Electron 应用。 | `capture_modes=["wait_render"]` 能等待；超时后返回 decision 而不是盲存。 |
| E10 | 动画/闪烁窗口 | 使用进度条、视频、广告动画页面。 | `wait_buffer` 报告 stable/timeout 样本；不会无限等待。 |
| E11 | 嵌套滚动容器 | 管理后台里滚动表格在 div/iframe 内。 | AI 选择 `capture_webpage mode=scroll_container`，不把桌面截图当全量数据。 |
| E12 | 网页路由禁用 | `webpage_capture=false` 时请求网页 capture。 | 返回 inactive/feature flag 信息，不偷偷启动浏览器依赖。 |
| E13 | hold-file 大量窗口 | `guardian_survey_windows capture_mode=hold_file capture_limit=3`。 | 只保存限制内文件；返回路径，避免把所有图塞进上下文。 |
| E14 | 运行时限制不可放宽 | 持久限制设得更紧，单次调用尝试放宽。 | 调用失败，说明不能 loosen persistent limits。 |
| E15 | Unicode 标题 | 选择“微信”“变色龙加速器”等中文窗口。 | 枚举、匹配、metadata JSON 无乱码。 |
| E16 | 输入畸形 | 无效 HWND、负 limit、错误 URL scheme。 | 返回结构化错误；不崩 MCP server。 |
| E17 | 清理安全 | `clear_cache` 指向非 Screen Guardian cache 目录。 | 跳过或拒绝，不能删任意文件。 |
| E18 | 前台不被抢 | 捕获前记录前台窗口，strict 捕获后再检查。 | 前台 HWND 不应因插件捕获而改变。 |
| E19 | 低信息但用户确认 | blank/white 画面用 `render_guard_confirmed=true`。 | 可以保存，但 metadata 必须保留 guard 证据和确认状态。 |
| E20 | 当前浏览器标签不可枚举 | 只调用本地 helper，不接 Chrome connector。 | `guardian_capture_targets` 应说明无法枚举用户浏览器会话，要求显式 URL 或外部 connector。 |
| E21 | 已登录浏览器会话里的嵌套滚动长图 | 认领当前 Chrome 中的授权页面，例如火山引擎费用中心；只读检测滚动容器，使用浏览器交互层滚动容器并分段截图拼接。 | 不读取 cookie/localStorage；不提交表单；分段截图后恢复滚动位置；metadata 标明 connector/session route、selector、segments、restored scroll；长图不能误称为 headless URL capture。 |

## 推荐执行顺序

1. 先跑静态和接口：

```powershell
node --check mcp\server.cjs
python -m py_compile scripts\screen_guardian_capture.py scripts\validate_contracts.py
npm run validate
```

2. 再跑普通 Windows smoke：

```powershell
npm run smoke:windows
```

3. 最后人工/半自动执行 E01-E21。E02、E05、E18 最能暴露“偷偷截可见屏幕”的问题；E21 最能暴露“登录态浏览器页面和普通 URL capture 混淆”的问题。

## 关键命令模板

目标索引：

```powershell
@'
{"action":"guardian_capture_targets","args":{"limit":20,"include_visibility_probe":true,"url":"https://example.com"}}
'@ | python scripts\screen_guardian_capture.py --stdin
```

严格后台窗口捕获：

```powershell
@'
{"action":"capture_window","args":{"hwnd":123456,"background_mode":"strict","quiet_preferred":true,"wait_for_nonblank":true,"render_guard":"warn","guard_checks":["unrendered","window_client_low_information","background_capture_unavailable"]}}
'@ | python scripts\screen_guardian_capture.py --stdin
```

明确可见屏幕兜底：

```powershell
@'
{"action":"capture_window","args":{"hwnd":123456,"background_mode":"visible_fallback","quiet_preferred":false,"render_guard":"warn","guard_checks":["unrendered","occlusion_risk","bbox_identity_mismatch"]}}
'@ | python scripts\screen_guardian_capture.py --stdin
```

已登录浏览器会话里的嵌套滚动长图：

```text
1. 通过 Chrome connector 认领用户已打开的授权标签页。
2. 只读检测 scrollHeight/clientHeight 或 scrollWidth/clientWidth。
3. 选择具体 selector，例如 .arco-table-content-inner。
4. 用浏览器交互层滚动该容器，而不是读取 cookie 或 localStorage。
5. 对容器 clip 分段截图，写入本地 cache。
6. 恢复原 scrollTop/scrollLeft。
7. 本地拼接长图，并把 selector、segments、restored 状态写入 metadata。
```

## 证据矩阵

| 路径 | 要看的证据 | 收敛条件 |
| --- | --- | --- |
| 通识 | Windows HWND/桌面可见像素是不同采集语义。 | strict 不应保存 visible bbox fallback。 |
| 代码 | `source.background_capture`、`capture_method`、guard issue IDs。 | 元数据和实际行为一致。 |
| 视觉 | 保存图像内容是否属于目标窗口。 | 图像不是覆盖窗口，也不是空白误导。 |
| 运行 | MCP 不崩、限制不被放宽、文件只写 cache。 | 失败可解释且可恢复。 |
| 浏览器会话 | 已登录页面只通过授权标签页和浏览器交互层读取。 | 不检查 token/cookie/localStorage，不把登录态 capture 伪装成无登录 URL capture。 |

## 逻辑漏洞清单

- 把“没有拉前台”误写成“所有窗口都可后台读到”。
- 把“bbox identity 采样通过”误写成“完全无遮挡”。
- 把“Chrome 窗口图像捕获”误写成“网页全量内容捕获”。
- 把 `ok=true` 误当成 `saved=true`。
- 把 `background_mode=visible_fallback` 的结果当成 strict 后台图形获取。
- 把“当前 Chrome 已登录标签页长图”误写成“无状态 headless URL 长图”。
- 为了拼接长图读取 cookie/localStorage；正确路线应该用用户已打开的授权标签页和浏览器交互层。

## 最小通过线

插件至少要通过 E01、E02、E05、E06、E12、E14、E16、E18，才算适合进入真实 AI 桌面工作流。E11 属于高级网页/DOM 路线，可以在网页捕获依赖启用后验收。E21 属于浏览器会话 connector/CDP 路线，适合在用户明确授权当前标签页时验收。
