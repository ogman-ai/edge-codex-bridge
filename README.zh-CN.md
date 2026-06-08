# Edge Codex Bridge

Edge Codex Bridge 是一个本地 Codex skill，用自定义 Native Messaging host 操作 Microsoft Edge 里的 Codex 浏览器扩展。

它主要用于 Edge 兼容性工作。脚本保留了 Chrome 兼容注册选项，因为 Edge 和 Chrome 共享 Chromium 扩展 API，但本项目不是官方 Codex Chrome backend。

## 功能

- 注册名为 `com.openai.codexextension` 的本地 Native Messaging host。
- 让 Codex 扩展通过 `scripts/host.cmd` 启动 `scripts/native_host.py`。
- 为 `scripts/client.py` 暴露仅限本机访问的控制桥。
- 通过扩展发送 JSON-RPC 请求和 Chrome DevTools Protocol 命令。
- 支持标签页列表、创建标签页、导航、DOM 检查、输入、截图、控制台事件、下载事件和清理。

## 要求

- Windows
- `python` 命令可用
- Microsoft Edge 已安装 Codex 浏览器扩展
- PowerShell，用于注册 native host

默认 Edge 扩展 ID：

```text
hehggadaopoacecdllhhajmbjkdcmajg
```

如有需要，可以给 `scripts/install_host.ps1` 传入其他扩展 ID。

## 安装

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_host.ps1
```

然后在 Edge 中重新加载 Codex 扩展，或等待扩展自动重连。

安装脚本会写入 `scripts/native_host_manifest.json`，并在当前用户的 Edge Native Messaging host 注册表项下注册它。

## 验证

```powershell
python .\scripts\client.py status
python .\scripts\client.py ping
python .\scripts\client.py info
```

如果 `status` 找不到 state 文件，说明浏览器扩展还没有启动 native host。重新加载扩展后再试。

## 基础用法

创建并检查标签页：

```powershell
$tab = python .\scripts\client.py create-tab | ConvertFrom-Json
python .\scripts\client.py attach --tab-id $tab.id
python .\scripts\client.py navigate --tab-id $tab.id https://example.com
python .\scripts\client.py title --tab-id $tab.id
python .\scripts\client.py text --tab-id $tab.id
```

接管并检查已有浏览器标签页：

```powershell
python .\scripts\client.py user-tabs
python .\scripts\client.py claim-user-tab --tab-id 123
python .\scripts\client.py attach --tab-id 123
python .\scripts\client.py title --tab-id 123
```

发送底层 CDP 命令：

```powershell
python .\scripts\client.py cdp --tab-id $tab.id --method Runtime.evaluate --params "{\"expression\":\"document.title\",\"returnByValue\":true}"
```

截图：

```powershell
python .\scripts\client.py screenshot --tab-id $tab.id --out .\tmp\page.png
```

收尾当前 bridge session 的浏览器标签页：

```powershell
python .\scripts\client.py finalize
```

## 卸载

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_host.ps1
```

卸载脚本只会在注册项指向本 skill 生成的 manifest 时删除它。只有在你明确想删除其他已有注册项时才使用 `-Force`。

## 安装到本地 Codex Skill 目录

把当前仓库的公开 skill 文件复制到本地 Codex skill 目录：

```powershell
.\install_skill.ps1
```

默认目标：

```text
%USERPROFILE%\.codex\skills\edge-codex-bridge
```

用 `-Target` 指定其他位置；用 `-Clean` 删除目标目录中不属于公开 skill 包的文件。

## 安全说明

- bridge 只监听 `127.0.0.1`。
- 本地 HTTP 控制桥使用临时 token，token 存在用户临时目录中。
- 读取浏览历史、接管已登录标签页、下载、上传、提交表单、发送消息、付款、删除或修改真实用户数据前，应先取得用户明确确认。
- 本项目使用 native host 名称 `com.openai.codexextension`；测试后如需恢复默认环境，请卸载。
- 剪贴板命令读写 Windows 系统剪贴板。

## 项目结构

```text
SKILL.md
README.md
README.zh-CN.md
agents/openai.yaml
references/protocol.md
scripts/client.py
scripts/native_host.py
scripts/host.cmd
scripts/install_host.ps1
scripts/uninstall_host.ps1
install_skill.ps1
```

JSON-RPC、CDP 和排障细节见 `references/protocol.md`。
