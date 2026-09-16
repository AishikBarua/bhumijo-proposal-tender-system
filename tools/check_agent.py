#!/usr/bin/env python3
"""
Is the AI Agent actually able to work?

Checks the four things the agent needs, in the order they matter, and says
plainly what is missing. Run it after putting your API key in .env, so you
find out here rather than by clicking "Process tender" and getting an error.

    python tools\\check_agent.py

It makes ONE very small API call (a few tokens, effectively free) to prove
the key really works — a key that is present but wrong or expired looks
identical to a good one until something tries to use it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing this loads .env into the environment, exactly as the server does.
from backend.config import settings  # noqa: E402,F401
from app import config as agent_config  # noqa: E402

LINE = "=" * 62
problems: list[str] = []


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


# --- 1. the key -------------------------------------------------------

def check_key() -> str | None:
    heading("1. Anthropic API key")
    key = agent_config.ANTHROPIC_API_KEY
    if not key:
        print("  [FAIL] not set")
        problems.append(
            "ANTHROPIC_API_KEY is not set.\n"
            "     Get one at console.anthropic.com, then add this line to\n"
            "     bhumijo_system\\.env :\n"
            "         ANTHROPIC_API_KEY=sk-ant-...")
        return None

    # Shape check before spending a call on something obviously wrong.
    if not key.startswith("sk-ant-"):
        print(f"  [WARN] set, but does not look like an Anthropic key "
              f"(starts '{key[:6]}…')")
    else:
        print(f"  [ OK ] set  (starts {key[:11]}…, {len(key)} characters)")
    return key


# --- 2. does it actually work ------------------------------------------

def check_call(key: str) -> None:
    heading("2. Can it reach Claude?")
    try:
        import anthropic
    except ImportError:
        print("  [FAIL] the anthropic package is not installed")
        problems.append("Run install.bat — the anthropic package is missing.")
        return

    model = agent_config.ANTHROPIC_MODEL_CHEAP
    print(f"  calling {model} with a 1-token request...")
    try:
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        print("  [ OK ] the key works — the AI Agent can process tenders")
    except Exception as exc:  # noqa: BLE001 — the message is the point
        name = type(exc).__name__
        print(f"  [FAIL] {name}: {exc}")
        text = str(exc).lower()
        if "authentication" in text or "401" in text or "invalid" in text and "key" in text:
            problems.append("The key was rejected. It is wrong, revoked, or from a "
                            "different account. Get a fresh one at console.anthropic.com.")
        elif "credit" in text or "billing" in text or "quota" in text:
            problems.append("The key is valid but the account has no credit. "
                            "Add credit at console.anthropic.com.")
        elif "not_found" in text or "model" in text:
            problems.append(f"The model name {model!r} was rejected. Set "
                            f"ANTHROPIC_MODEL_CHEAP in .env to a model your account has.")
        else:
            problems.append(f"Could not reach Anthropic: {exc}\n"
                            "     Check this machine has internet access.")


# --- 3. the company profile -------------------------------------------

def check_profile() -> None:
    heading("3. Company profile (what tenders are judged against)")
    from app.database import SessionLocal
    from app.models import CompanyProfile, Certification, PastContract

    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).first()
        if not profile or not (profile.sectors or "").strip():
            print("  [FAIL] no company profile")
            problems.append("Fill in Company profile in the agent — without it "
                            "every tender is judged against nothing.")
            return
        print(f"  [ OK ] {profile.company_name}")
        print(f"         sectors: {(profile.sectors or '')[:60]}")

        certs = db.query(Certification).count()
        contracts = db.query(PastContract).count()
        print(f"  {'[ OK ]' if certs else '[WARN]'} certifications: {certs}")
        print(f"  {'[ OK ]' if contracts else '[WARN]'} past contracts: {contracts}")

        if not certs or not contracts:
            problems.append(
                "Certifications and past contracts are empty.\n"
                "     The agent decides ELIGIBILITY from these. With none recorded it\n"
                "     cannot check requirements like '2 completed contracts of similar\n"
                "     nature' or 'BDT 5 crore turnover' — so it defaults to passing\n"
                "     everything. Add them under Company profile to make its verdicts real.")
    finally:
        db.close()


# --- 4. automatic email monitoring -------------------------------------

def check_email() -> None:
    heading("4. Automatic email monitoring (optional)")
    from app.database import SessionLocal
    from app.models import EmailSettings

    db = SessionLocal()
    try:
        s = db.query(EmailSettings).first()
        if not s or not s.imap_email:
            print("  [WARN] not configured — you can still add tenders by hand")
            print("         Set it up under 'Email settings' in the agent.")
            return
        print(f"  mailbox : {s.imap_email}")
        print(f"  enabled : {bool(s.enabled)}")
        print(f"  status  : {s.last_status or 'never run'}")
        if s.last_error:
            print(f"  [WARN] last error: {str(s.last_error)[:70]}")
    finally:
        db.close()


def main() -> int:
    print(LINE)
    print("  Can the AI Agent work?")
    print(LINE)

    key = check_key()
    if key:
        check_call(key)
    check_profile()
    check_email()

    print(f"\n{LINE}")
    if problems:
        print("  WHAT TO DO:\n")
        for p in problems:
            print(f"   - {p}\n")
    else:
        print("  Everything the AI Agent needs is in place.")
        print("  Paste a tender notice into the 'Add tender' page and try it.")
    print(LINE + "\n")
    return 1 if any("FAIL" in p or "not set" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
