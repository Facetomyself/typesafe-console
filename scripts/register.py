#!/usr/bin/env python3
"""Register a TypeSafe console account with a local Outlook mailbox and mint an API key."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from ruyipage import FirefoxOptions, FirefoxPage

PY = r"D:\reverse_ENV\.venv\Scripts\python.exe"
MAIL_CLI = r"D:\reverse_ENV\skill\outlook-mail-oauth\scripts\outlook_mail.py"
FIREFOX = r"D:\reverse_ENV\tools\ruyipage\runtimes\151-proxy\firefox\firefox.exe"
PICK = Path(r"D:\reverse_ENV\temp\typesafe-pick.json")
DUMP = Path(r"D:\reverse_ENV\temp\typesafe-login")
DUMP.mkdir(parents=True, exist_ok=True)
STORAGE = Path(r"D:\reverse_ENV\storage\typesafe-console")
LOGIN_URL = "https://console.typesafe.ai/login"
KEYS_URL = "https://console.typesafe.ai/keys"
KEY_NAME = "reverse-env"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    print(
        f"[dom] {name} url={snap.get('url')} buttons={[b.get('text') for b in snap.get('buttons') or []]}"
    )
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


def mail_poll(email: str, after: str) -> str:
    cmd = [
        PY,
        MAIL_CLI,
        "mail",
        "poll",
        "--account",
        email,
        "--after",
        after,
        "--match",
        "typesafe|TypeSafe|console.typesafe",
        "--timeout",
        "180",
        "--interval",
        "5",
        "--include-junk",
    ]
    print("[mail] polling")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"mail poll exit {proc.returncode}")
    data = json.loads(proc.stdout)
    if data.get("status") != "received" or not data.get("codes"):
        raise RuntimeError("no verification code")
    first = data["codes"][0]
    code = first.get("code") if isinstance(first, dict) else str(first)
    print("[mail] received code length", len(str(code)))
    (DUMP / "last-code-meta.json").write_text(
        json.dumps({"length": len(str(code)), "status": data.get("status")}, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(code)


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


def extract_api_key(page) -> str:
    secret = page.run_js(
        """
        return (function() {
          const reject = (v) => {
            if (!v) return true;
            if (v[0] === '{') return true;
            if (v.indexOf('N4Ig') === 0) return true;
            if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)) return true;
            return false;
          };
          const nodes = [...document.querySelectorAll('code, pre, input, textarea, [data-slot=input]')];
          for (const e of nodes) {
            const v = String(e.value || e.innerText || '').trim();
            if (reject(v)) continue;
            if (/^(ts_|sk_|tsk_|tsk-|ts-|sk-)/.test(v) && v.length >= 20) return v;
            if (v.length >= 32 && /^[A-Za-z0-9._\\-]+$/.test(v) && !v.includes('http')) return v;
          }
          const body = document.body.innerText || '';
          const patterns = [
            /\\bts_[A-Za-z0-9._-]{16,}\\b/,
            /\\bsk_[A-Za-z0-9._-]{16,}\\b/,
            /\\btsk_[A-Za-z0-9._-]{16,}\\b/,
            /\\bts-[A-Za-z0-9._-]{16,}\\b/
          ];
          for (const p of patterns) {
            const m = body.match(p);
            if (m && !reject(m[0])) return m[0];
          }
          return '';
        })();
        """
    )
    return str(secret or "")


def create_api_key(page) -> str:
    enter = page.ele("text=Enter console", timeout=2)
    if enter:
        print("[keys] Enter console first")
        enter.click()
        wait_url(page, lambda u: "/hook" not in u, timeout=15)
        time.sleep(1)
    page.get(KEYS_URL, timeout=45)
    wait_url(page, lambda u: "/keys" in u, timeout=20)
    time.sleep(2)
    dump_dom(page, "keys-before")
    if "/login" in page.url:
        raise RuntimeError(f"still on login when opening keys: {page.url}")
    if "/hook" in page.url or "/setup/" in page.url:
        raise RuntimeError(f"blocked before keys: {page.url}")

    body = (dump_dom(page, "keys-quiz") or {}).get("bodyText") or ""
    if "POP QUIZ" in body or "Can you chat with Jev" in body or "Can Jev talk" in body:
        nos = page.eles("text=No")
        print("[keys] No buttons", len(nos) if nos else 0)
        if not nos:
            raise RuntimeError("quiz No button missing")
        target = nos[-1]
        print("[keys] answering quiz with last No")
        target.click()
        deadline = time.time() + 15
        while time.time() < deadline:
            snap = dump_dom(page, "keys-quiz-wait")
            text = snap.get("bodyText") or ""
            if "POP QUIZ" not in text and "Waiting for your answer" not in text:
                break
            time.sleep(1)
        dump_dom(page, "keys-quiz-after")
        close_deadline = time.time() + 12
        while time.time() < close_deadline:
            snap = dump_dom(page, "keys-quiz-close-wait")
            text = snap.get("bodyText") or ""
            labels = [b.get("text") for b in snap.get("buttons") or []]
            if "Close" in labels:
                close_btn = page.ele("text=Close", timeout=2)
                if close_btn:
                    print("[keys] closing quiz overlay")
                    close_btn.click()
                    time.sleep(1.2)
            if "POP QUIZ" not in text and "THAT’S CORRECT" not in text and "THAT'S CORRECT" not in text:
                break
            time.sleep(0.6)
        if "/keys" not in (page.url or ""):
            print("[keys] returning to keys after overlay", page.url)
            page.get(KEYS_URL, timeout=45)
            wait_url(page, lambda u: "/keys" in u, timeout=20)
            time.sleep(1.2)
        dump_dom(page, "keys-quiz-closed")

    dialog = None
    for attempt in range(4):
        create_btn = page.ele("text=Create key", timeout=5)
        if not create_btn:
            raise RuntimeError("Create key button missing")
        print("[keys] clicking Create key attempt", attempt)
        create_btn.click()
        wait_deadline = time.time() + 8
        while time.time() < wait_deadline:
            dialog = dump_dom(page, "keys-dialog")
            inputs = dialog.get("inputs") or []
            if inputs:
                break
            time.sleep(0.5)
        if dialog and (dialog.get("inputs") or []):
            break
        time.sleep(0.8)
    if not dialog or not (dialog.get("inputs") or []):
        raise RuntimeError("Create key dialog did not open")
    name_box = (
        page.ele("#name", timeout=3)
        or page.ele("css:input[name=name]", timeout=1)
        or page.ele("css:input[type=text]", timeout=1)
    )
    if not name_box:
        raise RuntimeError("key name input missing")
    name_box.click()
    time.sleep(0.2)
    name_box.input(KEY_NAME)
    time.sleep(0.4)
    name_len = page.run_js(
        "return (function(){ const e=document.querySelector('#name'); return e ? String(e.value||'').length : 0; })();"
    )
    print("[keys] name length", name_len)
    if not name_len:
        raise RuntimeError("key name did not stick")
    creates = page.eles("text=Create key")
    print("[keys] Create key buttons", len(creates) if creates else 0)
    if not creates:
        raise RuntimeError("Create key confirm missing")
    print("[keys] confirm dialog Create key")
    creates[-1].click()
    secret = ""
    deadline = time.time() + 20
    while time.time() < deadline:
        dump_dom(page, "keys-after")
        secret = extract_api_key(page)
        if secret:
            break
        copy_btn = page.ele("text=Copy", timeout=1) or page.ele("text=Copy key", timeout=0.5)
        if copy_btn:
            copy_btn.click()
            time.sleep(0.4)
            secret = extract_api_key(page)
            if secret:
                break
        time.sleep(0.8)
    if not secret or secret.startswith("{") or secret.startswith("N4Ig"):
        raise RuntimeError("API key not visible after create")
    print("[keys] secret length", len(secret))
    return secret


def save_account(email: str, api_key: str, after: str) -> Path:
    STORAGE.mkdir(parents=True, exist_ok=True)
    payload = {
        "email": email,
        "api_key": api_key,
        "console": LOGIN_URL,
        "keys_url": KEYS_URL,
        "created_at": utc_now(),
        "mail_after": after,
        "source": "outlook-mail-oauth",
        "key_name": KEY_NAME,
    }
    path = STORAGE / "account.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (STORAGE / ".env").write_text(
        f"TYPESAFE_EMAIL={email}\nTYPESAFE_API_KEY={api_key}\n",
        encoding="utf-8",
    )
    print("[save]", path)
    return path


def main() -> None:
    pick = json.loads(PICK.read_text(encoding="utf-8"))
    email = pick["email"]
    profile = DUMP / f"profile-register-{int(time.time())}"
    opts = FirefoxOptions()
    opts.set_browser_path(FIREFOX)
    opts.set_user_dir(str(profile))
    page = FirefoxPage(opts)
    try:
        page.get(LOGIN_URL, timeout=45)
        time.sleep(1)
        dump_dom(page, "login")
        if on_setup(page.url):
            print("[resume] already on setup")
            accept_tos(page)
            api_key = create_api_key(page)
            save_account(email, api_key, utc_now())
            print("[done] saved")
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
        code = mail_poll(email, after)
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
        api_key = create_api_key(page)
        save_account(email, api_key, after)
        print("[done] saved")
    finally:
        try:
            page.browser.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
