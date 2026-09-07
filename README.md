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

**Purpose:** Download images from Instagram profiles using browser session authentication.

- **Key Features:** Browser cookie authentication, automatic retry on rate limits (429), Instaloader built-in skip-existing and rate limiting.
- **Usage:**
- `instabot <handler>`: Download all images from profile.
- `instabot <handler> --browser firefox`: Use Firefox cookies.
- `instabot <handler> --limit 10`: Download only first 10 posts.

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

#### 3. instabot - Retry Logic with Exponential Backoff ✅
**File:** `instabot/main.py`  
**Changes:**
- Added `import time` for sleep functionality
- Implemented retry loop with exponential backoff
- Specific handling for HTTP 429 (rate limit) errors
- Maximum retry limit to prevent infinite retries

```python
# New retry logic:
max_retries = 3
retry_count = 0
while retry_count < max_retries:
    try:
        subprocess.run(cmd, check=True)
        return
    except subprocess.CalledProcessError as e:
        if e.returncode == 429:  # Rate limit error
            wait_time = min(2 ** retry_count * 5, 60)  # Exponential backoff
            console.print(f"[yellow]⚠️  Rate limited (HTTP 429). Retrying in {wait_time} seconds...[/yellow]")
            time.sleep(wait_time)
        else:
            console.print(f"[bold red]Error: {e}[/bold red]")
            break
    
    retry_count += 1
```
**Impact:** Better handling of rate limits and transient errors, improved user experience

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

### Testing

A comprehensive test suite (`test_improvements.py`) validates all improvements:

```bash
python3 test_improvements.py
```

Tests for:
- ✅ aicap regex duplicate removal
- ✅ ostris timeout handling improvement  
- ✅ instabot retry logic addition
- ✅ copycat privacy disclaimer presence

### Impact Assessment

**Criticality Level:** High  
These fixes address:
1. **Code correctness** (duplicate patterns)
2. **Reliability** (timeout handling, retry logic)
3. **User experience** (rate limit handling, privacy transparency)
4. **Maintainability** (better error handling patterns)

**No Breaking Changes:** All improvements are backward compatible and do not change the public API of any tool.

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
