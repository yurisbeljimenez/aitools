# 🧰 AI Tools Monorepo

**A portable, user-agnostic collection of professional-grade AI CLI utilities.**

This repository houses a suite of independent tools designed to manage AI workflows (Training, Inference, Data Ingestion) on Linux systems. The architecture prioritizes **portability**, **isolation**, and **standardization**.

---

## 🏗️ Architecture & Golden Rules

To maintain portability across different machines (e.g., migrating from `tensor` to a new rig) and users (`master` vs `ubuntu`), all tools **MUST** adhere to the following strict implementation rules.

### 1. Zero External Dependencies (The "Island" Rule)

Each tool folder (e.g., `hugin/`, `aicap/`) must be **completely self-contained**.

- **No Shared Venvs:** Every tool gets its own `venv`. We trade disk space for stability. If Tool A breaks its dependencies, Tool B must remain unaffected.
- **No Shared Code:** Do not import modules from neighboring tool folders.

### 2. User Agnostic Paths

**NEVER** hardcode `/home/master` or `/usr/local/bin` inside the Python code.

- ✅ **Do:** Use `Path.home()` or `Path.cwd()` to resolve paths dynamically.
- ❌ **Don't:** `path = "/home/master/ai/tools"`

### 3. The "Shebang" Patching Protocol

Tools are deployed via symbolic links. To ensure the link points to the correct virtual environment on the target machine:

- Python scripts must start with a generic shebang: `#!/usr/bin/env python3`.
- The `install_all.sh` script is responsible for rewriting this line to point to the **local absolute path** of the tool's venv during installation.

### 4. Standardized UX

All tools must utilize the same stack for a consistent look and feel:

- **CLI Parsing:** `Typer`
- **UI/Logging:** `Rich` (Panels, Tables, Progress Bars)
- **Configuration:** Arguments/Flags preferred over config files.

---

## 🚀 Installation & Migration

This repository is designed to be cloned anywhere. The `install_all.sh` script handles the heavy lifting of setting up environments and linking commands globally.

```bash
# 1. Clone the repo
git clone https://github.com/yurisbeljimenez/aitools.git ~/ai/tools

# 2. Run the Universal Installer
cd ~/ai/tools
chmod +x install_all.sh
./install_all.sh
```

**What the installer does:**

1. Scans every tool folder.
2. Deletes old/broken virtual environments.
3. Rebuilds a fresh `venv` and installs `requirements.txt` (with progress bars).
4. Patches the `main.py` entry point to use the absolute path of the new venv.
5. Creates/Overwrites symbolic links in `/usr/local/bin`.

---

## 🛠️ Tool Reference

### 🦅 `hugin` (Hugging Face Manager)

**Purpose:** Comprehensive Hugging Face cache and repository management.

- **Key Features:** Turbo downloads (Rust-based), cache visualization, safe deletion, cache cleaning, and Hugging Face API integration.
- **Commands:**
- `hugin ls`: Dashboard of downloaded models with sorting and filtering.
- `hugin pull <repo_id>`: Accelerated download with glob patterns and revision support.
- `hugin nuke <repo_id>`: Delete a model to free space (supports fuzzy matching).
- `hugin space`: Disk usage report for system and Hugging Face cache.
- `hugin clean`: Clean hanging/dangling items from cache (dangling files and refs).
- `hugin deep-clean`: Deep clean cache by removing old revisions and unused files.
- `hugin files <repo_id>`: List files in a repository with sizes.
- `hugin download <repo_id> <filename>`: Download specific files from repositories.
- `hugin user`: Show current Hugging Face user information.
- `hugin repos`: List user's repositories with filtering by type.

### 🤖 `aicap` (Dataset Captioner)

**Purpose:** Auto-caption image datasets for LoRA training using Florence-2.

- **Key Features:** Local inference (no API), detailed captioning, batch processing.
- **Usage:**
- `aicap <folder_path> <trigger_word>`
- _Example:_ `aicap ./my_dataset novak4i`

### 🛋️ `comfy` (Process Manager)

**Purpose:** Manage the ComfyUI server instance.

- **Key Features:** Detached background running, log streaming, Port 9000 safety lock.
- **Usage:**
- `comfy start`: Launch server (checks if port is free).
- `comfy stop`: Graceful shutdown.
- `comfy status`: Check PID and URL.
- `comfy logs`: Tail the log file.

### 🛡️ `ostris` (Training Manager)

**Purpose:** Manage the Ostris AI Toolkit (Flux Training).

- **Key Features:** **GPU Lock (Port 9000)** prevents running training if ComfyUI is active. Handles recursive process killing to stop `npm` auto-restarts.
- **Usage:**
- `ostris start`: Launch the Web UI.
- `ostris stop`: Kill the UI and all training workers.

### 🐱 `copycat` (Reference Ingest)

**Purpose:** Download high-quality video references for AI mimicry.

- **Key Features:** Browser cookie theft (for auth), AI-ready Markdown metadata, auto-renaming.
- **Usage:**
- `copycat <URL>`: Download video to current folder.
- `copycat <URL> --browser firefox`: Use Firefox cookies.

### 📸 `instabot` (Instagram Ingestor)

**Purpose:** Download an Instagram **profile**, or a **single Reel/post URL**, using your browser session.

- **Key Features:** Browser session authentication (looks like a human, not a bot), Reel/post URL support, **anti-flagging** design — no wrapper retry loop, so a rate limit *aborts* the run instead of hammering the API (protects the account), clean resume on re-run via `--fast-update`, downloads to the current folder by default.
- **Usage:**
- `instabot <handler>`: Download a profile's photo archive to `./<handler>/`.
- `instabot https://www.instagram.com/reel/<code>/`: Download a single Reel/post to the current folder.
- `instabot <handler> --browser firefox`: Use Firefox cookies.
- `instabot <handler> --limit 10`: Download only the first 10 posts.
- `instabot <handler> --print-cmd`: Print the exact instaloader command without running it.

---

## 🔧 Improvements & Maintenance

### Recent Enhancements

This section documents recent improvements made to fix critical bugs and enhance error handling across all tools.

#### 1. aicap - Duplicate Regex Pattern Removal ✅
**File:** `aicap/main.py`  
**Issue:** Lines 141-142 contained duplicate regex patterns for mood sentence scrubbing  
**Fix:** Removed the duplicate pattern, leaving only one instance  
```python
# Before (lines 141-142):
r"The overall mood of the image is [a-zA-Z\s]+\.$",
r"The overall mood of the image is [a-zA-Z\s]+\."  # DUPLICATE!

# After (line 141):
r"The overall mood of the image is [a-zA-Z\s]+\."  # Single instance
```
**Impact:** Prevents unnecessary processing and potential performance overhead

#### 2. ostris - Enhanced Port Waiting Logic ✅
**File:** `ostris/main.py`  
**Issue:** Infinite loop potential in port waiting logic without proper termination check  
**Fix:** Added attempt counter with max_retries boundary check  
```python
# Before:
while not is_port_busy(PORT):
    check = get_port_process(PORT)
    if check and "node" in check.name().lower():
        break
    time.sleep(1)

# After:
attempts = 0
for _ in range(max_retries):
    check = get_port_process(PORT)
    if check and "node" in check.name().lower():
        return
    
    attempts += 1
    if attempts >= max_retries:
        break
    
    time.sleep(1)
```
**Impact:** Prevents infinite loops, improves reliability during server startup

#### 3. instabot - Anti-Flagging Design (retry loop REMOVED) ✅
**File:** `instabot/main.py`  
**Issue:** A wrapper-level retry loop with exponential backoff was exactly the behaviour that gets an account flagged by Instagram — re-hitting the API on a 429 is the opposite of what a human does.
**Fix:** Removed the retry loop entirely. We now lean on instaloader's own conservative knobs so a rate limit **ABORTS** the run instead of retrying, and a later re-run resumes cleanly via `--fast-update`. Single source of truth: the official `instaloader`.
```python
# Anti-bot / "do not re-attempt" flags passed to instaloader:
"--load-cookies", browser,          # browser session => looks like a human
"--max-connection-attempts", "1",   # 1 attempt => no connection-level retry
"--abort-on", "429",                # rate limit ABORTS the run instead of retrying
```
**Impact:** Protects the account from being flagged; clean, resumable downloads; no duplicated download logic

#### 4. copycat - Privacy Disclaimer Addition ✅
**File:** `copycat/main.py`  
**Change:** Added privacy disclaimer to docstring for cookie usage  
```python
"""
Download video reference and generate AI-ready metadata.

Uses yt_dlp for efficient single-call metadata extraction and download.
Supports YouTube, TikTok, Instagram, and 1000+ other sites.

⚠️  PRIVACY NOTE: Cookie theft is used for authenticated content access only.
No cookies are stored or transmitted beyond the yt-dlp download process.
"""
```
**Impact:** Improved transparency about cookie usage, better user trust

#### 5. ostris - Safe Supervisor Kill (never kills your shell) ✅
**File:** `ostris/main.py`  
**Issue:** `ostris stop` climbed the process tree with a substring test `"sh" in name`, which also matched `bash`/`zsh` — so it could **SIGKILL your interactive shell**. The `"npm" in name` branch could never match (npm runs as `node`).
**Fix:** Replaced it with a precise `is_safe_supervisor()` classifier plus an explicit `NEVER_KILL_NAMES` blocklist (bash, zsh, fish, ksh, tmux, screen, init, …). Only recognized supervisors (npm / concurrently / a plain POSIX `sh`) are killed, and the walk stops at the first non-supervisor.
```python
NEVER_KILL_NAMES = {"bash", "zsh", "fish", "ksh", "csh", "tcsh",
                    "tmux", "screen", "init", "systemd", "login", "sshd"}
# npm detected via cmdline (it runs as `node`), never via a name substring.
```
**Impact:** `ostris stop` is safe to run from any shell; the user's session can no longer be killed by the tool.

#### 6. aicap - Removed Invalid `timeout` Keyword Argument ✅
**File:** `aicap/main.py`  
**Issue:** `model.generate(..., timeout=60)` — `timeout` is not a valid `generate()` parameter, so it was either silently swallowed or crashed the model's `forward`. The comment ("Prevent hangs") was misleading: it did nothing.
**Fix:** Removed the kwarg (and its comment).
**Impact:** Correct, documented `generate()` call; no spurious crash path.

#### 7. Installer & Tests — User-Agnostic Paths + Honest Failures ✅
**Files:** `install_all.sh`, `test_improvements.py`  
**Issue:** The installer used `Path.cwd()` (broke depending on where it was run) and silently reported "🎉 Sync Complete!" even when tools failed; the test suite hardcoded `/home/master` paths.
**Fix:** Anchor both to `Path(__file__).resolve().parent`; the installer now collects failures, lists them, and exits non-zero on any failure; `os.geteuid()` is guarded for non-POSIX systems.
**Impact:** Works on any user/machine; a partial failure is now reported as a failure.

### Testing

A comprehensive test suite (`test_improvements.py`) validates all improvements:

```bash
python3 test_improvements.py
```

Tests for:
- ✅ aicap — exactly one mood pattern, no invalid `timeout` kwarg
- ✅ ostris — bounded `start()` timeout handling
- ✅ ostris — supervisor killer never targets interactive shells
- ✅ instabot — anti-flagging design (no retry loop; abort-on 429; browser cookies)
- ✅ copycat — privacy disclaimer presence

### Impact Assessment

**Criticality Level:** High  
These fixes address:
1. **Safety** — `ostris stop` no longer risks SIGKILL'ing your interactive shell; `instabot` no longer hammers Instagram (removed retry loop).
2. **Code correctness** — duplicate regex removed; invalid `timeout=` kwarg removed from `model.generate()`.
3. **Reliability** — bounded `start()` health-check; clean, resumable `instabot` downloads; honest failure reporting in the installer.
4. **Maintainability** — user-agnostic paths (no hardcoded `/home/master`); tests run from any working directory.

**Compatibility note:** `instabot` now intentionally does *not* auto-retry on rate limits (this is the fix, not a regression); re-run the command later to resume.

### Future Recommendations

1. **Add unit tests** for each tool's core functionality
2. **Implement CI pipeline** with linting (flake8) and type checking (mypy)
3. **Add integration tests** for port collision scenarios
4. **Document common troubleshooting issues** in this README
5. **Consider shared base requirements** to reduce duplication between tools

```text
~/ai/tools/
├── install_all.sh          # The Migration Script (The only shared logic)
├── README.md               # This file
├── hugin/
│   ├── main.py             # Entry point
│   ├── requirements.txt    # Dependencies (typer, rich, hf_transfer)
│   └── venv/               # (GitIgnored) Isolated Environment
├── aicap/
│   ├── main.py
│   └── requirements.txt    # Dependencies (torch, transformers, pillow)
├── comfy/
│   ├── main.py
│   └── requirements.txt    # Dependencies (psutil)
├── ostris/
│   ├── main.py
│   └── requirements.txt    # Dependencies (psutil)
├── instabot/
│   ├── main.py
│   └── requirements.txt    # Dependencies (instaloader, browser-cookie3)
└── copycat/
    ├── main.py
    └── requirements.txt    # Dependencies (yt-dlp)
```
