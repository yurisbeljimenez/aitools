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

---

## 📂 Directory Structure

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
│   └── requirements.py     # Dependencies (psutil)
└── copycat/
    ├── main.py
    └── requirements.txt    # Dependencies (yt-dlp)
```
