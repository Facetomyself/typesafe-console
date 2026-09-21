# TypeSafe Console

独立维护 [TypeSafe Console](https://console.typesafe.ai/) 的账号开通自动化。当前发布面是浏览器自动化版本：使用本机 Outlook 邮箱完成注册、邮件确认与 API key 创建，并将邮箱与密钥配对写入本机存储。

仓库：<https://github.com/Facetomyself/typesafe-console>

## 当前范围

本仓库交付控制台账号开通，不覆盖 TypeSafe SDK 集成，也不覆盖对 `console.typesafe.ai` 的协议还原。HTTP API 调用以官方文档为准：<https://docs.typesafe.ai/api.md>。

| 项 | 说明 |
|----|------|
| 发布面 | 浏览器自动化开通（ruyipage Firefox 151） |
| 登录方式 | 邮箱一次性验证码（`Email me a code instead`） |
| 邮件确认 | 本机 `outlook-mail-oauth` 轮询 Graph / IMAP |
| API key | 控制台 `/keys` 创建；默认密钥名 `reverse-env` |
| 凭据落点 | 本机存储目录，不进入 Git |
| 协议复现 | 搁置。后续若做独立协议客户端，另开工作面 |

2026-09-21 已在本机完成一次端到端开通：OTP 登录、服务条款与 onboarding、密钥页测验、创建 API key，配对文件已写入本地存储。

## 开通流程

1. 从本机 Outlook 库存取出一封已验证、IMAP 可用的邮箱。
2. 打开 `https://console.typesafe.ai/login`，填入邮箱，选择邮件验证码。
3. 轮询收件箱（含 Junk），将 6 位验证码填回 `/login?otp=true`。
4. 新账号完成 `/setup/tos`、姓名与问卷（可 Skip），进入控制台。
5. 打开 `/keys`。首次创建前可能出现 Jev 测验（“Can you chat with Jev?” 答案为 No）；关闭结果层后再点 Create key。
6. 在对话框填写密钥名并确认。脚本将邮箱与 API key 写入本机 `account.json` 与 `.env`。

控制台输入为 React 受控组件，须使用原生 `input()` / `click()`。页面上的 “Help us improve Jev” Yes/No 与测验按钮并存，测验取最后一个 No。

## 运行

脚本依赖本机 `reverse_ENV` 内的 Python venv、ruyipage 151-proxy 与 `outlook-mail-oauth` 状态池，不安装到系统全局。

```powershell
$py = "D:\reverse_ENV\.venv\Scripts\python.exe"
$proj = "D:\reverse_ENV\workspace\typesafe-console"

# 选择邮箱（只写邮箱地址与协议，不含 token）
# 示例：D:\reverse_ENV\temp\typesafe-pick.json
# {"email":"<mailbox@outlook.com>","protocol":"imap"}

& $py "$proj\scripts\register.py"
```

运行前确认：

- `outlook-mail-oauth` 中目标账号 `last_verify_status=verified`，且 `mail list` 可通。IMAP 报 `User is authenticated but not connected` 时换下一封已验证邮箱。
- 选择文件位于 `D:\reverse_ENV\temp\typesafe-pick.json`。
- Firefox 路径为 `D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe`。

每次运行使用新的 Firefox profile，避免复用旧会话落到 setup 页。会话级 DOM 快照写在 `D:\reverse_ENV\temp\typesafe-login\`，不进入本仓库。

## 本机产物

| 路径 | 内容 |
|------|------|
| `D:\reverse_ENV\storage\typesafe-console\account.json` | 邮箱、API key、控制台 URL、创建时间 |
| `D:\reverse_ENV\storage\typesafe-console\.env` | `TYPESAFE_EMAIL` / `TYPESAFE_API_KEY` |
| `D:\reverse_ENV\temp\typesafe-pick.json` | 本次选用的邮箱地址 |
| `D:\reverse_ENV\temp\typesafe-login\` | DOM 快照与一次性 Firefox profile |

邮箱地址、验证码、refresh token、API key 和浏览器 profile 不得提交，不得写入 issue，不得出现在 README 正文。

## 仓库结构

```text
scripts/register.py   开通自动化入口
AGENTS.md             本仓协作边界
.env.example          本机环境变量字段名（无真实值）
LICENSE               MIT
```

Public 仓只跟踪说明、脚本、许可证和忽略规则。原始证据、Cookie、密钥、邮件正文留在本机。

## 许可

MIT License。见 [LICENSE](./LICENSE)。
