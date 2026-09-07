#!/usr/bin/env python3
"""
Test script to validate the improvements made to the AI tools.
This tests:
1. aicap - duplicate regex removal
2. ostris - timeout handling improvement  
3. instabot - retry logic addition
4. copycat - privacy disclaimer addition
"""

import re
import sys
from pathlib import Path

def test_aicap_regex_fix():
    """Test that aicap no longer has duplicate regex patterns."""
    print("Testing aicap regex fix...")
    
    aicap_path = Path("/home/master/Documents/aitools/aicap/main.py")
    content = aicap_path.read_text()
    
    # Count occurrences of the mood pattern text (simpler approach)
    mood_pattern_text = "The overall mood of the image is"
    matches = content.count(mood_pattern_text)
    
    if matches == 1:
        print("✅ PASS: aicap has exactly one mood pattern reference (duplicate removed)")
        return True
    else:
        print(f"❌ FAIL: aicap has {matches} mood pattern references (expected 1)")
        return False

def test_ostris_timeout_improvement():
    """Test that ostris has improved timeout handling."""
    print("\nTesting ostris timeout improvement...")
    
    ostris_path = Path("/home/master/Documents/aitools/ostris/main.py")
    content = ostris_path.read_text()
    
    # Check for the attempts counter
    has_attempts_counter = "attempts += 1" in content
    has_max_retries_check = "if attempts >= max_retries:" in content
    
    if has_attempts_counter and has_max_retries_check:
        print("✅ PASS: ostris has improved timeout handling with attempt counter")
        return True
    else:
        print(f"❌ FAIL: ostris missing timeout improvements (attempts_counter={has_attempts_counter}, max_retries_check={has_max_retries_check})")
        return False

def test_instabot_retry_logic():
    """Test that instabot has retry logic."""
    print("\nTesting instabot retry logic...")
    
    instabot_path = Path("/home/master/Documents/aitools/instabot/main.py")
    content = instabot_path.read_text()
    
    # Check for key components of retry logic
    has_max_retries = "max_retries" in content
    has_retry_loop = "while retry_count < max_retries:" in content
    has_exponential_backoff = "2 ** retry_count" in content
    has_time_import = "import time" in content
    
    if all([has_max_retries, has_retry_loop, has_exponential_backoff, has_time_import]):
        print("✅ PASS: instabot has complete retry logic with exponential backoff")
        return True
    else:
        missing = []
        if not has_max_retries: missing.append("max_retries")
        if not has_retry_loop: missing.append("retry loop")
        if not has_exponential_backoff: missing.append("exponential backoff")
        if not has_time_import: missing.append("time import")
        print(f"❌ FAIL: instabot missing retry components: {missing}")
        return False

def test_copycat_privacy_disclaimer():
    """Test that copycat has privacy disclaimer."""
    print("\nTesting copycat privacy disclaimer...")
    
    copycat_path = Path("/home/master/Documents/aitools/copycat/main.py")
    content = copycat_path.read_text()
    
    # Check for privacy-related keywords
    has_privacy_note = "PRIVACY" in content or "privacy" in content
    has_cookie_disclaimer = "cookie" in content.lower() and ("disclaimer" in content.lower() or "note" in content.lower())
    
    if has_privacy_note and has_cookie_disclaimer:
        print("✅ PASS: copycat has privacy disclaimer for cookie usage")
        return True
    else:
        print(f"❌ FAIL: copycat missing privacy disclaimer (privacy={has_privacy_note}, cookie_disclaimer={has_cookie_disclaimer})")
        return False

def main():
    """Run all tests and report results."""
    print("=" * 60)
    print("Testing AI Tools Improvements")
    print("=" * 60)
    
    tests = [
        test_aicap_regex_fix,
        test_ostris_timeout_improvement,
        test_instabot_retry_logic,
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