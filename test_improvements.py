#!/usr/bin/env python3
"""
Test script to validate the current design of the AI tools.
This tests:
1. aicap    - exactly one mood-regex reference AND no invalid `timeout` kwarg
2. ostris   - start() health-check timeout handling is present
3. ostris   - the supervisor killer NEVER targets interactive shells (bash/zsh/...)
4. instabot - anti-flagging design: NO wrapper retry loop; abort-on 429; browser cookies
5. copycat  - privacy disclaimer is present

All paths are anchored to this file's directory (user/location agnostic),
so the suite works on /home/master, /home/ubuntu, /srv, etc.
"""

import re
import sys
from pathlib import Path

# Anchor to THIS file's directory — no more hardcoded /home/master.
ROOT = Path(__file__).resolve().parent


def test_aicap_clean_generate():
    """Test aicap: exactly one mood pattern and no invalid `timeout` kwarg."""
    print("Testing aicap generate() hygiene...")

    content = (ROOT / "aicap" / "main.py").read_text()

    # Exactly one reference to the mood-sentence pattern.
    mood_pattern_text = "The overall mood of the image is"
    matches = content.count(mood_pattern_text)

    # `timeout=` is NOT a valid kwarg for model.generate(); it must be gone.
    has_invalid_timeout = "timeout=" in content

    if matches == 1 and not has_invalid_timeout:
        print("✅ PASS: aicap has one mood pattern and no invalid timeout kwarg")
        return True

    print(
        f"❌ FAIL: aicap mood_pattern_refs={matches} (expected 1), "
        f"invalid_timeout_kwarg={has_invalid_timeout} (expected False)"
    )
    return False


def test_ostris_timeout_improvement():
    """Test that ostris start() has bounded health-check timeout handling."""
    print("\nTesting ostris start() timeout handling...")

    content = (ROOT / "ostris" / "main.py").read_text()

    has_attempts_counter = "attempts += 1" in content
    has_max_retries_check = "if attempts >= max_retries:" in content

    if has_attempts_counter and has_max_retries_check:
        print("✅ PASS: ostris has bounded timeout handling with attempt counter")
        return True

    print(
        "❌ FAIL: ostris missing timeout improvements "
        f"(attempts_counter={has_attempts_counter}, max_retries_check={has_max_retries_check})"
    )
    return False


def test_ostris_safe_kill():
    """Test that ostris stop() NEVER kills interactive shells / tmux / screen."""
    print("\nTesting ostris safe supervisor kill...")

    content = (ROOT / "ostris" / "main.py").read_text()

    # The old, dangerous substring check must be gone.
    dangerous_old_check = '"sh" in name' in content
    # A precise classifier + an explicit never-kill list must be present.
    has_never_kill = (
        "NEVER_KILL_NAMES" in content
        and "bash" in content
        and "zsh" in content
    )
    has_classifier = "is_safe_supervisor" in content

    if (not dangerous_old_check) and has_never_kill and has_classifier:
        print("✅ PASS: ostris uses a precise supervisor classifier and protects shells")
        return True

    print(
        "❌ FAIL: ostris "
        f"dangerous_substring_check={dangerous_old_check} (expected False), "
        f"never_kill_list={has_never_kill} (expected True), "
        f"classifier={has_classifier} (expected True)"
    )
    return False


def test_instabot_antiflagging():
    """Test that instabot does NOT hammer Instagram (no wrapper retry loop).

    The old design wrapped instaloader in a retry-with-backoff loop, which is
    exactly the behaviour that gets an account flagged. The correct design is
    the opposite: one attempt, abort on 429, resume later via --fast-update.
    """
    print("\nTesting instabot anti-flagging design...")

    content = (ROOT / "instabot" / "main.py").read_text()

    # The old, dangerous wrapper-level retry loop must be GONE.
    no_retry_loop = (
        "while retry_count < max_retries:" not in content
        and "2 ** retry_count" not in content
    )
    # Anti-bot knobs and the rest of the intended design must be present.
    has_max_attempts = "--max-connection-attempts" in content
    has_abort_on = '"--abort-on"' in content and "429" in content
    has_browser_session = "--load-cookies" in content
    has_reel_parsing = "classify_target" in content

    if all([no_retry_loop, has_max_attempts, has_abort_on, has_browser_session, has_reel_parsing]):
        print("✅ PASS: instabot is anti-flagging (no retry loop; abort-on 429; cookies; Reel parsing)")
        return True

    missing = []
    if not no_retry_loop: missing.append("removed retry loop")
    if not has_max_attempts: missing.append("max-connection-attempts")
    if not has_abort_on: missing.append("abort-on 429")
    if not has_browser_session: missing.append("load-cookies")
    if not has_reel_parsing: missing.append("Reel URL parsing")
    print(f"❌ FAIL: instabot missing anti-flagging pieces: {missing}")
    return False


def test_instabot_target_disambiguation():
    """A bare word is ALWAYS a profile; only a '-'-prefixed token is a shortcode.

    Regression guard: 'novak4i' (a username containing a digit) must NOT be
    misclassified as a bare shortcode.
    """
    print("\nTesting instabot target disambiguation...")

    content = (ROOT / "instabot" / "main.py").read_text()

    # The old, ambiguous 'username-with-a-digit == shortcode' heuristic is gone.
    no_ambiguous = "any(c.isdigit() for c in t)" not in content
    # The explicit dash-prefixed shortcode convention is present.
    has_dash_convention = 't.startswith("-")' in content
    # Bare words always fall through to profile.
    has_profile_fallback = 'return "profile", t' in content

    if no_ambiguous and has_dash_convention and has_profile_fallback:
        print("✅ PASS: bare word = profile; dash-prefixed = shortcode (unambiguous)")
        return True

    print(
        "❌ FAIL: instabot target disambiguation "
        f"(no_ambiguous={no_ambiguous}, dash_convention={has_dash_convention}, "
        f"profile_fallback={has_profile_fallback})"
    )
    return False


def test_copycat_privacy_disclaimer():
    """Test that copycat has a privacy disclaimer."""
    print("\nTesting copycat privacy disclaimer...")

    content = (ROOT / "copycat" / "main.py").read_text()

    has_privacy_note = "PRIVACY" in content or "privacy" in content
    has_cookie_disclaimer = (
        "cookie" in content.lower()
        and ("disclaimer" in content.lower() or "note" in content.lower())
    )

    if has_privacy_note and has_cookie_disclaimer:
        print("✅ PASS: copycat has privacy disclaimer for cookie usage")
        return True

    print(
        "❌ FAIL: copycat missing privacy disclaimer "
        f"(privacy={has_privacy_note}, cookie_disclaimer={has_cookie_disclaimer})"
    )
    return False


def main():
    """Run all tests and report results."""
    print("=" * 60)
    print("Testing AI Tools Improvements")
    print("=" * 60)

    tests = [
        test_aicap_clean_generate,
        test_ostris_timeout_improvement,
        test_ostris_safe_kill,
        test_instabot_antiflagging,
        test_instabot_target_disambiguation,
        test_copycat_privacy_disclaimer,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ ERROR in {test.__name__}: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Improvements are working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
