# TypeSafe Console

本仓库提供 [TypeSafe Console](https://console.typesafe.ai/) 的账号注册自动化。当前发布面是浏览器自动化：读取 Outlook 四参数邮箱文件，完成邮箱 OTP 登录与新账号 onboarding。

仓库：<https://github.com/Facetomyself/typesafe-console>

## 范围

本仓库只做控制台账号注册。不覆盖 TypeSafe SDK 集成，也不覆盖对 `console.typesafe.ai` 的协议还原。HTTP API 调用以官方文档为准：<https://docs.typesafe.ai/api.md>。

| 项 | 说明 |
|----|------|
| 发布面 | 浏览器自动化注册（ruyipage Firefox 151） |
| 登录方式 | 邮箱一次性验证码（`Email me a code instead`） |
| 邮件确认 | 最小 IMAP XOAUTH2 轮询（INBOX，必要时 Junk） |
| 协议复现 | 搁置。后续若做独立协议客户端，另开工作面 |

## 邮箱文件

脚本从本地 txt 读取 **一条** Outlook 记录。每行四个字段，以 `----` 分隔：

```text
email----password----client_id----refresh_token
```

| 字段 | 说明 |
|------|------|
| `email` | Outlook 邮箱地址，例如 `name@outlook.com` |
| `password` | 占位字段，注册流程不使用 |
| `client_id` | Microsoft Entra 公共客户端 ID |
| `refresh_token` | 已授权的 refresh token，用于换取 IMAP 访问令牌 |

空行、`#` 注释行以及首行 `卡密导出` 会被跳过。默认读取仓库旁的 `mailbox.txt`（已忽略，不进 Git），也可用 `--mailbox` 指定路径。

## 注册流程

1. 打开 `https://console.typesafe.ai/login`，填入 txt 中的邮箱，选择邮件验证码。
2. 用该行的 `client_id` / `refresh_token` 刷新 IMAP 访问令牌，轮询收件箱（含 Junk），将 6 位验证码填回 `/login?otp=true`。
3. 新账号完成 `/setup/tos`、姓名与问卷（可 Skip），进入控制台。

控制台输入为 React 受控组件，须使用原生 `input()` / `click()`。

## 运行

脚本依赖本机 `reverse_ENV` 内的 Python venv 与 ruyipage 151-proxy。

```powershell
$py = "D:\reverse_ENV\.venv\Scripts\python.exe"
$proj = "D:\reverse_ENV\workspace\typesafe-console"

& $py "$proj\scripts\register.py"
& $py "$proj\scripts\register.py" --mailbox "D:\path\to\mailbox.txt"
```

运行前确认：

- `mailbox.txt` 为上述四参数格式，且 refresh token 仍可换取 IMAP 访问令牌。
- Firefox 路径为 `D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`。

每次运行使用新的 Firefox profile。会话级 DOM 快照写在 `D:\reverse_ENV\temp\typesafe-login\`，不进入本仓库。

## 仓库结构

```text
scripts/register.py   注册自动化入口
LICENSE               MIT
```

Public 仓只跟踪说明、脚本、许可证和忽略规则。邮箱 txt、refresh token、验证码和浏览器 profile 留在本机。

## 许可

MIT License。见 [LICENSE](./LICENSE)。
