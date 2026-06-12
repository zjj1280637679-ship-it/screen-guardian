# 授权嗅探层

`guardian_sniff_context` 是一个只做路线判断的 AI-first 入口。它用于回答一个问题：在用户已经声明的授权范围内，下一步最适合走哪条路线。

它不是网络抓包，不是浏览器密钥读取器，也不是数据库/注册表扫描器。默认行为是只返回候选路线和边界说明。

## 设计目标

- 在截图前先判断是否有更高效的授权路线。
- 区分可见像素、窗口图形、浏览器会话、网页 URL、嵌套滚动容器、文档转换、导出/API、数据库、注册表等不同语义。
- 把“用户给了更高授权”降级理解为“可以推荐更多候选路线”，而不是“自动执行敏感读取”。
- 对图里提到的 MarkItDown 类工具，归类为“授权文件转 Markdown/结构化文本”路线，不把它混同为 cookie、localStorage、浏览器会话或账号密钥路线。

## 授权等级

| 等级 | 含义 | 可以推荐的主要路线 | 默认禁止 |
| --- | --- | --- | --- |
| `L0_visual_only` | 默认视觉路线 | 目标索引、屏幕/窗口截图、hold-file | DOM 读数、表单提交、导出、cookie、localStorage、数据库、注册表 |
| `L1_current_page_readonly` | 当前页面只读 | 浏览器会话只读 DOM、嵌套滚动检测、会话内截图 | 表单提交、下载导出、浏览器密钥存储、数据库、注册表 |
| `L2_page_interaction` | 页面交互 | 打开筛选、翻页、授权文件转换、需要确认的导出入口 | 破坏性提交、权限变更、购买、浏览器密钥存储、数据库、注册表 |
| `L3_sensitive_action_confirmed` | 已确认敏感动作 | 已确认导出、只读 API、文件转换 | 凭据读取、浏览器密钥存储、数据库/注册表写入 |
| `L4_sensitive_storage_or_data_access` | 明确的数据源访问 | 只读数据库、只读注册表、只读 API | 未限定范围的修改、密钥外泄、凭据打印 |

## 路线候选

| 路线 | 适合场景 | 执行前要求 |
| --- | --- | --- |
| `guardian_capture_targets` | 先看可截图显示器、窗口、显式网页目标 | 无截图、无导航 |
| `capture_window` strict | 不想被遮挡影响的应用窗口图形获取 | 目标 HWND 或精确窗口匹配 |
| `browser_connector_current_tab` | 已登录浏览器页面，当前标签状态有价值 | `L1_current_page_readonly`，不读 cookie/localStorage/sessionStorage |
| `browser_session_nested_scroll` | 页面内表格、面板、iframe 需要完整长图 | 明确 selector，记录分段和恢复滚动状态 |
| `capture_webpage` | 显式 URL 且不依赖用户当前登录会话 | 网页捕获功能开启 |
| `markitdown_style_optional_adapter` | 用户授权的本地 PDF、Office、图片等文件更适合转 Markdown | `file_convert` 授权，只读用户给出的文件 |
| `authorized_export_download` | 页面提供导出按钮，用户明确确认导出 | `L3_sensitive_action_confirmed` |
| `api_readonly` | 用户提供明确只读 API 端点和范围 | `L3_sensitive_action_confirmed` |
| `database_readonly` | 用户明确给出只读连接和查询范围 | `L4_sensitive_storage_or_data_access` |
| `registry_readonly` | 用户明确给出只读注册表 key 范围 | `L4_sensitive_storage_or_data_access` |

## 返回契约

`guardian_sniff_context` 必须保持这些字段语义：

- `sniff_performed=true`
- `capture_performed=false`
- `secret_storage_read=false`
- `database_or_registry_touched=false`
- `network_request_performed=false`
- `route_candidates` 只代表候选路线，不代表已经执行
- `recommended_order` 只代表排序，不代表授权已经充分
- `authorization.allowed_actions` / `recommendable_actions` 只代表后续工具可考虑的动作
- `authorization.performed_actions=[]` 表示本次嗅探没有执行截图、滚动、导出、API、数据库或注册表动作

## 示例

```json
{
  "action": "guardian_sniff_context",
  "args": {
    "objective": "在已登录控制台里获取嵌套表格完整长图",
    "authorization_level": "L1_current_page_readonly",
    "declared_permissions": ["dom_measure", "container_scroll", "screenshot"],
    "target": {
      "kind": "browser_tab",
      "title": "费用中心",
      "selector": ".arco-table-content-inner"
    }
  }
}
```

预期结论是优先推荐浏览器会话只读路线和嵌套滚动长图路线，同时明确禁止读取 cookie、localStorage、sessionStorage。

如果传入 `file_paths`，嗅探层只做路径字符串、扩展名和本地元数据分类，不读取文件内容。潜在网络路径，例如 UNC 或 `file://` 路径，默认跳过元数据探测；只有显式设置 `allow_network_file_metadata_probe=true` 才允许后续实现考虑探测。

## 因果降级

- “用户授权当前页面只读”只说明浏览器会话只读路线可能可用，不说明可以读取浏览器密钥存储。
- “文档可以被 MarkItDown 类工具转换”只说明文件转换路线可能更高效，不说明可以读取未授权文件。
- “数据库只读路线存在”只说明在 `L4` 且范围明确时可以作为候选，不说明网页任务需要或应该碰数据库。
- “路线排序靠前”只说明执行成本可能更低，不说明证据质量一定更高。

## 最小验收

1. 调用后不生成图片文件。
2. 调用后不导航网页、不滚动页面、不下载文件。
3. 调用后不读取 cookie、localStorage、sessionStorage、密码库。
4. 调用后不连接数据库、不读取注册表。
5. 对文件路径只做元数据/扩展名分类，除非后续工具在用户授权下执行转换。
6. 对潜在网络路径默认返回 `metadata_probe_skipped="potential_network_path"`。
