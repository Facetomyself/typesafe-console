# AGENTS.md

## 仓库边界

本目录是 `reverse_ENV/workspace/typesafe-console`。独立 Public 仓，只提交 README、AGENTS、开通脚本和忽略规则。

## 强制规则

- 禁止提交邮箱地址、验证码、API key、`.env`、`account.json`、Cookie、浏览器 profile、DOM 快照全文。
- 凭据只写 `D:\reverse_ENV\storage\typesafe-console\`。
- 会话临时文件只写 `D:\reverse_ENV\temp\typesafe-login\`。
- 当前主线是浏览器自动化开通。协议复现搁置，不要在本仓起 RuyiTrace case 或 vanilla TLS 客户端。
- 新文本使用 UTF-8 without BOM + LF。
- 回复中只报告邮箱与密钥长度/前缀，不回显验证码和完整 API key。
- 邮件轮询只用 `outlook-mail-oauth` CLI；token 留在 DPAPI 状态目录。
