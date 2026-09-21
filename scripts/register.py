#!/usr/bin/env python3
"""Register a TypeSafe console account with Outlook mailbox OTP."""

from __future__ import annotations

import argparse
import html
import imaplib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from ruyipage import FirefoxOptions, FirefoxPage

PY_FIREFOX = r"D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe"
DUMP = Path(r"D:\reverse_ENV\temp\typesafe-login")
DUMP.mkdir(parents=True, exist_ok=True)
LOGIN_URL = "https://console.typesafe.ai/login"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_HOST = "outlook.office365.com"
IMAP_SCOPE = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"
CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
MAIL_MATCH = re.compile(r"typesafe|console\.typesafe", re.IGNORECASE)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAILBOX = ROOT / "mailbox.txt"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_mailbox_txt(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot read mailbox file: {path}") from exc
    for number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text or text.startswith("#") or text == "卡密导出":
            continue
        fields = text.split("----")
        if len(fields) != 4 or not all(fields):
            raise RuntimeError(f"invalid Outlook record at line {number}: expect email----password----client_id----refresh_token")
        email, _password, client_id, refresh_token = fields
        return {
            "email": email.strip(),
            "client_id": client_id.strip(),
            "refresh_token": refresh_token.strip(),
        }
    raise RuntimeError("mailbox txt contains no Outlook records")


def refresh_access_token(client_id: str, refresh_token: str) -> str:
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": IMAP_SCOPE,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"token refresh failed: {detail}") from exc
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("token refresh returned no access_token")
    return token


def imap_login(email: str, access_token: str) -> imaplib.IMAP4_SSL:
    client = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=20)
    payload = f"user={email}\x01auth=Bearer {access_token}\x01\x01".encode("utf-8")
    client.authenticate("XOAUTH2", lambda _: payload)
    return client


def message_text(raw: bytes) -> tuple[str, datetime | None]:
    parsed = BytesParser(policy=policy.default).parsebytes(raw)
    parts: list[str] = []
    for part in parsed.walk():
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        content = part.get_content()
        parts.append(content if isinstance(content, str) else str(content))
    body = "\n".join(parts)
    subject = str(make_header(decode_header(parsed.get("Subject", ""))))
    sender = str(make_header(decode_header(parsed.get("From", ""))))
    received = parsed.get("Date", "")
    try:
        date = parsedate_to_datetime(received)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        received_at = date.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        received_at = None
    text = html.unescape(re.sub(r"<[^>]+>", " ", f"{subject} {sender} {body}"))
    return text, received_at


def folder_codes(client: imaplib.IMAP4_SSL, folder: str, after: datetime, limit: int = 20) -> list[str]:
    status, _ = client.select(folder, readonly=True)
    if status != "OK":
        return []
    status, values = client.uid("search", None, "ALL")
    if status != "OK":
        return []
    found: list[str] = []
    for uid in reversed((values[0] or b"").split()[-limit:]):
        status, fetched = client.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK":
            continue
        raw = b"".join(item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes))
        if not raw:
            continue
        text, received_at = message_text(raw)
        if received_at is not None and received_at < after:
            continue
        if not MAIL_MATCH.search(text):
            continue
        match = CODE_RE.search(text)
        if match:
            found.append(match.group(1))
    return found


def poll_otp(email: str, client_id: str, refresh_token: str, after_iso: str, timeout: int = 180, interval: int = 5) -> str:
    after = datetime.fromisoformat(after_iso.replace("Z", "+00:00"))
    deadline = time.time() + timeout
    print("[mail] polling IMAP")
    while time.time() < deadline:
        token = refresh_access_token(client_id, refresh_token)
        client = imap_login(email, token)
        try:
            codes = folder_codes(client, "INBOX", after)
            if not codes:
                codes = folder_codes(client, "Junk", after)
            if codes:
                print("[mail] received code length", len(codes[0]))
                return codes[0]
        finally:
            try:
                client.logout()
            except Exception:
                pass
        time.sleep(interval)
    raise RuntimeError("no verification code")


def dump_dom(page, name: str) -> dict:
    snap = page.run_js(
        """
        return (function() {
          const visible = (e) => {
            const s = window.getComputedStyle(e);
            const r = e.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width + r.height > 0;
          };
          const buttons = [...document.querySelectorAll('button, a, [role=button]')].filter(visible).map(e => ({
            tag: e.tagName,
            type: e.type || '',
            id: e.id || '',
            name: e.name || '',
            text: (e.innerText || e.textContent || '').trim().slice(0, 160),
            href: e.href || ''
          }));
          const inputs = [...document.querySelectorAll('input, textarea')].filter(visible).map(e => ({
            tag: e.tagName,
            type: e.type || '',
            id: e.id || '',
            name: e.name || '',
            placeholder: e.placeholder || '',
            valueLen: String(e.value || '').length
          }));
          return {
            url: location.href,
            title: document.title,
            buttons,
            inputs,
            bodyText: (document.body.innerText || '').slice(0, 4000)
          };
        })();
        """
    )
    (DUMP / f"{name}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[dom] {name} url={snap.get('url')}")
    return snap


def wait_url(page, pred, timeout=30) -> str:
    deadline = time.time() + timeout
    url = ""
    while time.time() < deadline:
        url = page.url
        if pred(url):
            return url
        time.sleep(0.4)
    return url


def logged_in(url: str) -> bool:
    return "console.typesafe.ai" in url and "/login" not in url


def on_setup(url: str) -> bool:
    return "/setup/" in (url or "")


def accept_tos(page) -> None:
    dump_dom(page, "tos-before")
    legal = page.ele("#legal", timeout=5)
    if legal:
        legal.click()
        time.sleep(0.4)
        print("[tos] clicked #legal")
    else:
        box = page.ele("css:input[name=legalAcknowledged]", timeout=2)
        if box:
            box.click()
            print("[tos] clicked legalAcknowledged")
    cont = page.ele("text=Continue", timeout=5)
    if not cont:
        raise RuntimeError("TOS Continue missing")
    cont.click()
    wait_url(page, lambda u: "/setup/tos" not in u, timeout=20)
    time.sleep(1.2)
    dump_dom(page, "tos-after")


def finish_setup(page) -> None:
    for i in range(8):
        if not on_setup(page.url):
            break
        dump_dom(page, f"setup-{i}")
        skipped = False
        for label in ("Skip", "Continue", "Next", "Submit", "Finish", "Get started"):
            btn = page.ele(f"text={label}", timeout=1.2)
            if btn:
                print("[setup]", page.url, "->", label)
                btn.click()
                skipped = True
                time.sleep(1.4)
                break
        if not skipped:
            break
    enter = page.ele("text=Enter console", timeout=3)
    if enter:
        print("[setup] Enter console")
        enter.click()
        wait_url(page, lambda u: "/hook" not in u and "/setup/" not in u, timeout=20)
        time.sleep(1.5)
    dump_dom(page, "setup-done")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a TypeSafe console account")
    parser.add_argument(
        "--mailbox",
        default=str(DEFAULT_MAILBOX),
        help="Outlook txt: email----password----client_id----refresh_token",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mailbox = parse_mailbox_txt(Path(args.mailbox))
    email = mailbox["email"]
    profile = DUMP / f"profile-register-{int(time.time())}"
    opts = FirefoxOptions()
    opts.set_browser_path(PY_FIREFOX)
    opts.set_user_dir(str(profile))
    page = FirefoxPage(opts)
    try:
        page.get(LOGIN_URL, timeout=45)
        time.sleep(1)
        dump_dom(page, "login")
        if on_setup(page.url):
            print("[resume] already on setup")
            accept_tos(page)
            finish_setup(page)
            print("[done] registered")
            return
        email_box = page.ele("#email", timeout=10)
        if not email_box:
            raise RuntimeError("email input missing")
        email_box.input(email)
        after = utc_now()
        code_btn = page.ele("text=Email me a code instead", timeout=5)
        if not code_btn:
            raise RuntimeError("email-code button missing")
        code_btn.click()
        wait_url(page, lambda u: "otp=true" in u, timeout=15)
        time.sleep(1)
        dump_dom(page, "after-send")
        code = poll_otp(email, mailbox["client_id"], mailbox["refresh_token"], after)
        code_box = page.ele("#code", timeout=10)
        if not code_box:
            raise RuntimeError("code input missing")
        code_box.input(code)
        time.sleep(0.4)
        verify = page.ele("text=Verify", timeout=5)
        if not verify:
            raise RuntimeError("verify button missing")
        verify.click()
        wait_url(page, logged_in, timeout=20)
        time.sleep(2)
        dump_dom(page, "after-verify")
        if not logged_in(page.url):
            raise RuntimeError(f"verify did not leave login: {page.url}")
        if "/setup/tos" in page.url:
            accept_tos(page)
        finish_setup(page)
        dump_dom(page, "after-onboarding")
        print("[done] registered")
    finally:
        try:
            page.browser.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
