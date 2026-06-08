# Virtual Environment Migration — Implementation Guide

Use this document on your **development PC** with Cursor to migrate the project from global/system Python to a project-local `.venv`.

---

## Cursor prompt (copy and paste)

```
Implement the virtual-environment migration described in docs/VENV_MIGRATION.md.

Requirements:
- Follow the plan in order (Phase 1 → Phase 2 → Phase 3).
- Keep user-facing batch-file messages in Chinese, matching existing scripts.
- Do not change application Python code unless the doc explicitly requires it.
- After edits, verify batch-file logic and update README.md as specified.
- Do not commit unless I ask.
```

---

## How to use this document in Cursor (dev PC)

Follow this workflow on your **development machine**:

### Step 1 — Open the project in Cursor

Clone or open the repo, then open `docs/VENV_MIGRATION.md` in the editor so Cursor can reference it.

### Step 2 — Run the venv migration

Paste the **Cursor prompt** (above) into Cursor chat. Cursor should:

1. Create `scripts/env.bat`
2. Update `install.bat`, `run.bat`, `build_app.bat`
3. Update `README.md`
4. Leave `src/**` application code unchanged (unless you also request startup optimizations — see Section 16)

### Step 3 — Install dependencies into `.venv`

In a terminal at the project root:

```bat
install.bat
```

Expected result: a `.venv` folder is created and all dependencies are installed inside it.

### Step 4 — Select the Cursor Python interpreter

1. Open Command Palette → **Python: Select Interpreter**
2. Choose: `.venv\Scripts\python.exe`

If it is not listed, choose **Enter interpreter path** and browse to `.venv\Scripts\python.exe`.

### Step 5 — Verify daily workflow

```bat
run.bat
```

Or in a Cursor terminal (after `.venv\Scripts\activate`):

```bat
python -m japanese_subtitle.app.gui
python -m pytest
```

### Step 6 — (Optional) Fix slow startup

If the GUI still feels slow after venv migration, run the **startup optimization prompt** in Section 16.

### Step 7 — Build the Windows app (when ready)

```bat
build_app.bat
```

Ship `dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe` to end users. They do **not** need Python or `.venv`.

---

## 1. Background

### Review verdict

The migration plan **does solve the system-vs-virtual-environment problem** if implemented with the refinements below:

- Use `.venv\Scripts\python.exe` / `python -m pip` everywhere after bootstrap.
- Stop `run.bat` from installing packages automatically.
- Make `run.bat` and `build_app.bat` fail if `.venv` is missing.
- Enforce a dependency-compatible Python version when creating `.venv`.

The migration plan **does not fully solve slow startup by itself**. It removes one major launcher bottleneck only if `run.bat` is changed to avoid the heavy ML import check. The remaining startup fixes require small changes in `gui.py` and `pipeline_config.py`; those are described separately in Section 16.

### Current state

The project installs and runs against **whatever `python` / `pip` is on PATH**:

| File | Current behavior |
|------|------------------|
| `install.bat` | Calls global `python` and `pip`; installs PyTorch + project deps into system/user site-packages |
| `run.bat` | Calls global `python` / `pythonw`; may auto-install deps globally if imports fail |
| `build_app.bat` | Calls global `python`, `pip`, and `pyinstaller` |
| `README.md` | Documents global `pip install` workflow |
| `.gitignore` | Already ignores `.venv/` but no venv is created or used |

### Problems on non-dev machines

- Different PCs may have different Python versions (e.g. 3.9 vs 3.14).
- Dependencies pollute the global Python environment.
- `run.bat` auto-install can silently install into the wrong environment.
- Reproducibility between dev, test, and build machines is poor.

### Target state

| Audience | Environment |
|----------|-------------|
| **Developers** | Project-local `.venv` created by `install.bat`, used by all `.bat` scripts |
| **End users** | Standalone `dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe` (unchanged) |

---

## 2. Design decisions

1. **Use stdlib `venv`** — no Poetry, conda, or `uv` required; keeps Windows `.bat` workflow simple.
2. **Venv path** — `<project-root>/.venv/`
3. **Never commit `.venv`** — already in `.gitignore`.
4. **Global Python is bootstrap only** — used once to run `python -m venv .venv`; all installs and runs use `.venv\Scripts\python.exe`.
5. **Fail fast** — if `.venv` is missing, tell the user to run `install.bat` instead of falling back to global Python.
6. **Remove `run.bat` auto-install** — dependency installation belongs in `install.bat` only.
7. **Use a dependency-compatible Python** — prefer Python **3.11** on Windows. Do not create the venv from Python 3.14 unless all ML dependencies are confirmed to support it.

### Python version policy

This project says `requires-python = ">=3.9"`, but heavy ML dependencies such as `torch`, `qwen-asr`, `transformers`, and `PySide6` may lag behind the latest Python release. A venv created from an unsupported Python version will still fail.

Recommended policy:

| Python version | Recommendation |
|----------------|----------------|
| 3.11 | Best default for this project |
| 3.10 / 3.12 | Usually acceptable |
| 3.9 | Allowed by project metadata, but older |
| 3.13+ / 3.14 | Avoid unless dependencies are verified |

For Windows developer machines, prefer creating the venv with:

```bat
py -3.11 -m venv .venv
```

If the Python launcher is unavailable, use a known-good `python.exe` from Python 3.10–3.12.

---

## 3. Files to change

| Priority | File | Action |
|----------|------|--------|
| 1 | `scripts/env.bat` | **Create** — shared venv path resolution |
| 2 | `install.bat` | **Update** — create venv, install inside it |
| 3 | `run.bat` | **Update** — require venv, launch via `pythonw` in venv |
| 4 | `build_app.bat` | **Update** — build using venv Python |
| 5 | `README.md` | **Update** — document venv workflow |
| 6 | `.gitignore` | **Verify** — `.venv/` already present; no change expected |

**Do not change** (unless a bug is found during testing):

- `src/**` application code
- `pyproject.toml` / `requirements.txt` dependency lists
- `packaging/subtitle_app.spec`

---

## 4. Phase 1 — Create `scripts/env.bat`

Create `scripts/env.bat` as the single source of truth for venv paths.

### Responsibilities

1. `cd /d "%~dp0\.."` — resolve project root (parent of `scripts/`).
2. Set:
   - `VENV_DIR=%CD%\.venv`
   - `PY=%VENV_DIR%\Scripts\python.exe`
   - `PYW=%VENV_DIR%\Scripts\pythonw.exe`
3. Expose a check function or inline logic other scripts can call.

### Suggested implementation

```bat
@echo off
REM Resolve project root (parent of scripts/)
cd /d "%~dp0\.."

set "ROOT=%CD%"
set "VENV_DIR=%ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PYW=%VENV_DIR%\Scripts\pythonw.exe"

REM Usage: call scripts\env.bat [require]
REM   require = fail if .venv is missing
if /i "%~1"=="require" (
    if not exist "%PY%" (
        echo 错误：未找到虚拟环境
        echo 请先运行 install.bat 安装依赖
        exit /b 1
    )
)
```

### Notes for implementer

- Use `call scripts\env.bat require` from `run.bat` and `build_app.bat`.
- Use `call scripts\env.bat` (no arg) from `install.bat` before venv exists.
- Always `call` this script; do not `start` it.
- After `call scripts\env.bat require`, the caller must check `if errorlevel 1 exit /b 1`. A called batch file returning `exit /b 1` does **not** automatically stop the parent script.

Example:

```bat
call scripts\env.bat require
if errorlevel 1 (
    pause
    exit /b 1
)
```

---

## 5. Phase 1 — Update `install.bat`

### New flow

```
1. call scripts\env.bat
2. Select bootstrap Python:
   - prefer `py -3.11` if available
   - otherwise use `python` only if version is 3.10–3.12 (or at minimum >=3.9 and dependency-compatible)
3. If .venv missing → %BOOTSTRAP_PY% -m venv .venv
4. Re-call scripts\env.bat require (or re-set PY after creation), then check errorlevel
5. "%PY%" -m pip install -U pip setuptools wheel
6. Install PyTorch via "%PY%" -m pip (CUDA cu128, fallback to CPU)
7. "%PY%" -m pip install -e ".[dev]" (fallback: requirements.txt)
8. Verify imports with "%PY%" -c "import ..."
9. Print Torch/CUDA info with "%PY%"
10. Check ffmpeg (unchanged)
```

### Replace all bare commands

| Before | After |
|--------|-------|
| `python` | `%PY%` (after venv exists) or global `python` only for `python -m venv` |
| `pip install ...` | `"%PY%" -m pip install ...` |
| `pip uninstall ...` | `"%PY%" -m pip uninstall ...` |

### Suggested top-of-file addition

After `chcp 65001` and the header echo, add:

```bat
cd /d "%~dp0"
call scripts\env.bat
```

Before creating `.venv`, choose and validate the bootstrap interpreter:

```bat
set "BOOTSTRAP_PY=python"
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set "BOOTSTRAP_PY=py -3.11"
)

%BOOTSTRAP_PY% -c "import sys; raise SystemExit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo 错误：当前 Python 版本不适合本项目依赖
    echo 建议安装 Python 3.11，并确保 py -3.11 可用
    pause
    exit /b 1
)
```

Then add venv creation:

```bat
if not exist "%PY%" (
    echo.
    echo 正在创建虚拟环境 .venv ...
    %BOOTSTRAP_PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo 错误：虚拟环境创建失败
        pause
        exit /b 1
    )
    echo 虚拟环境创建完成 ✓
)

call scripts\env.bat require
if errorlevel 1 (
    pause
    exit /b 1
)
echo 使用 Python：%PY%
```

Then replace every remaining `pip` / `python` (except the bootstrap interpreter used to create `.venv`) with `"%PY%" -m pip` / `"%PY%"`.

Also add a venv sanity check after creation:

```bat
"%PY%" -c "import sys; print('Python:', sys.executable); print('In venv:', sys.prefix != sys.base_prefix)"
if errorlevel 1 (
    echo 错误：虚拟环境 Python 无法运行
    pause
    exit /b 1
)
```

### User-facing message updates

Add after successful install:

```bat
echo 依赖已安装到项目虚拟环境：.venv
echo 启动程序请运行 run.bat
```

---

## 6. Phase 1 — Update `run.bat`

### New flow

```
1. cd /d "%~dp0"
2. call scripts\env.bat require, then check errorlevel
3. "%PY%" -c "import japanese_subtitle, PySide6" → quick check; if fail, tell user to run install.bat (do NOT auto pip install)
4. ffmpeg warning (unchanged)
5. Launch GUI with %PYW% if exists, else %PY%
```

### Key changes

- **Remove** the block that runs `pip install -e .` or `pip install -r requirements.txt`.
- **Remove** the global `python --version` check; `env.bat require` covers missing venv.
- **Do not** import `torch`, `transformers`, `qwen_asr`, `sklearn`, or `resemblyzer` in `run.bat`. Those imports are the biggest startup delay.
- **Replace** launch commands:

```bat
call scripts\env.bat require
if errorlevel 1 (
    pause
    exit /b 1
)

"%PY%" -c "import japanese_subtitle, PySide6" >nul 2>&1
if errorlevel 1 (
    echo 缺少必要依赖。
    echo 请运行 install.bat 安装依赖到虚拟环境。
    pause
    exit /b 1
)

if exist "%PYW%" (
    start "" "%PYW%" -m japanese_subtitle.app.gui
) else (
    start "" "%PY%" -m japanese_subtitle.app.gui
)
```

### New error message when imports fail

```bat
echo 缺少必要依赖。
echo 请运行 install.bat 安装依赖到虚拟环境。
```

---

## 7. Phase 1 — Update `build_app.bat`

### New flow

```
1. cd /d "%~dp0"          (already present)
2. call scripts\env.bat require, then check errorlevel
3. "%PY%" scripts\generate_icon.py
4. "%PY%" -m pip install pyinstaller
5. "%PY%" -m PyInstaller packaging\subtitle_app.spec --noconfirm
```

### Replace

| Before | After |
|--------|-------|
| `python scripts\generate_icon.py` | `"%PY%" scripts\generate_icon.py` |
| `pip install pyinstaller` | `"%PY%" -m pip install pyinstaller` |
| `pyinstaller packaging\...` | `"%PY%" -m PyInstaller packaging\subtitle_app.spec --noconfirm` |

Using `python -m PyInstaller` ensures the module runs from the venv even if `pyinstaller.exe` is not on PATH.

Add this near the top after `cd /d "%~dp0"`:

```bat
call scripts\env.bat require
if errorlevel 1 (
    pause
    exit /b 1
)
```

---

## 8. Phase 2 — Update `README.md`

Update these sections:

### `## 环境要求`

Add:

```markdown
- 开发时会在项目根目录自动创建 `.venv` 虚拟环境（无需手动管理）
```

### `## 安装步骤`

Replace step 3–4 with:

```markdown
3. 安装依赖（推荐）：
   - 双击运行 `install.bat`
   - 脚本会自动创建 `.venv` 并在其中安装依赖
   - 会优先安装 CUDA 版 PyTorch，失败时自动回退
4. 手动安装（仅开发调试用）：
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `python -m pip install -U pip`
   - `python -m pip install -e ".[dev]"`
```

### `## 开发启动方式`

Update commands:

```markdown
- 双击 `run.bat`（使用 `.venv`）
- `.venv\Scripts\python.exe -m japanese_subtitle.app.gui`
```

CLI:

```markdown
- `.venv\Scripts\python.exe -m japanese_subtitle.app.cli`
```

### `## 常见问题排查`

Update item 1:

```markdown
1. **依赖问题**：重新运行 `install.bat`（会重建/更新 `.venv` 内依赖）
```

Add:

```markdown
6. **提示未找到虚拟环境**：先运行 `install.bat`，再运行 `run.bat`
```

### Optional: Cursor / IDE section (new)

```markdown
## Cursor / VS Code 开发

1. 先运行 `install.bat`
2. 在 Cursor 中选择解释器：`.venv\Scripts\python.exe`
3. 终端中激活虚拟环境：`.venv\Scripts\activate`
4. 运行测试：`.venv\Scripts\python.exe -m pytest`
```

---

## 9. Phase 3 — Optional improvements (after Phase 1 works)

Only implement if Phase 1 is stable:

1. **`setup.bat`** — thin wrapper that only calls `install.bat` (alias for discoverability).
2. **Venv rebuild flag** — `install.bat --recreate` deletes `.venv` and reinstalls (useful when switching Python versions).
3. **`uv`** — faster installs; defer unless install time is a pain point.

---

## 10. Implementation order for Cursor

Execute in this exact order to avoid broken intermediate states:

```
Step 1: Create scripts/env.bat
Step 2: Update install.bat
Step 3: Update run.bat
Step 4: Update build_app.bat
Step 5: Update README.md
Step 6: Verify Python version and venv interpreter (Section 11)
Step 7: Manual test checklist (Section 11)
```

---

## 11. Manual test checklist

Run on a **clean clone** or after deleting `.venv`:

### Test A — Fresh install

```bat
install.bat
```

Expected:

- [ ] `.venv\` folder created
- [ ] `.venv\Scripts\python.exe` exists
- [ ] `.venv\Scripts\python.exe -c "import sys; print(sys.version); print(sys.prefix != sys.base_prefix)"` prints `True`
- [ ] Venv Python is 3.10–3.12, preferably 3.11
- [ ] Import check passes
- [ ] Torch/CUDA info printed
- [ ] No packages installed to global Python (optional: check `python -m pip list` vs `.venv\Scripts\python.exe -m pip list`)

### Test B — Run app

```bat
run.bat
```

Expected:

- [ ] GUI launches
- [ ] No `pip install` during launch
- [ ] If `.venv` deleted first → clear error: run `install.bat`

### Test C — Missing venv

1. Delete `.venv`
2. Run `run.bat`

Expected:

- [ ] Fails with message to run `install.bat`
- [ ] Does not use global Python

### Test D — Build

```bat
build_app.bat
```

Expected:

- [ ] Icon generation succeeds
- [ ] PyInstaller build succeeds
- [ ] `dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe` runs

### Test E — Cursor interpreter

In Cursor:

1. Open Command Palette → **Python: Select Interpreter**
2. Choose `.venv\Scripts\python.exe`
3. Run: `python -m pytest`

Expected:

- [ ] Tests run with venv interpreter
- [ ] Imports resolve without `PYTHONPATH` hacks

---

## 12. Success criteria

Migration is complete when:

1. `install.bat` creates and populates `.venv` automatically.
2. `run.bat` and `build_app.bat` never call bare global `python` / `pip` for project work.
3. `run.bat` does not auto-install dependencies.
4. `.venv` is created from a dependency-compatible Python version, preferably Python 3.11.
5. README documents the venv workflow and Cursor interpreter path.
6. End-user PyInstaller workflow is unchanged.
7. All items in Section 11 pass.

---

## 13. Rollback plan

If something breaks:

1. Delete `.venv`
2. Revert batch files from git: `git checkout -- install.bat run.bat build_app.bat`
3. Delete `scripts/env.bat` if created
4. Old global-Python workflow works again (not recommended long term)

---

## 14. What stays the same

- **End users** still run `JapaneseSubtitleGenerator.exe`; they do not need Python or `.venv`.
- **FFmpeg** remains a system dependency (or bundled in `ffmpeg\` for PyInstaller).
- **Model download** behavior is unchanged.
- **`pyproject.toml`** dependency definitions are unchanged.

---

## 15. Quick reference

| Task | Command |
|------|---------|
| First-time setup | `install.bat` |
| Daily dev launch | `run.bat` |
| Activate venv in terminal | `.venv\Scripts\activate` |
| GUI (manual) | `.venv\Scripts\python.exe -m japanese_subtitle.app.gui` |
| CLI (manual) | `.venv\Scripts\python.exe -m japanese_subtitle.app.cli` |
| Tests | `.venv\Scripts\python.exe -m pytest` |
| Build Windows app | `build_app.bat` |
| Cursor interpreter | `.venv\Scripts\python.exe` |

---

## 16. Application startup time — what is happening?

This section explains **why the app feels slow to open**, and lists optional fixes you can ask Cursor to implement later.

> **Important:** Slow startup is **not caused by loading ASR/MT models**. Models load only when you click **生成字幕**. The delay happens earlier — during launcher checks and Python import time.

### 16.1 Startup timeline (current behavior)

When you double-click `run.bat`, this is what happens **before the window appears**:

```text
run.bat
  │
  ├─ [A] python --version check
  │
  ├─ [B] Heavy import pre-check  ← MAJOR bottleneck
  │     python -c "import japanese_subtitle, torch, transformers,
  │                  accelerate, tokenizers, safetensors, sentencepiece,
  │                  qwen_asr, PySide6, opencc, numpy, sklearn, resemblyzer"
  │     (loads PyTorch, Transformers, Qwen ASR, scikit-learn, etc.)
  │
  ├─ [C] ffmpeg -version check
  │
  └─ [D] start pythonw -m japanese_subtitle.app.gui
        │
        ├─ [E] Import chain loads AGAIN  ← second major bottleneck
        │     gui.py
        │       ├─ import torch          (PyTorch DLLs + CUDA init)
        │       ├─ import PySide6        (Qt libraries)
        │       └─ import SubtitleService
        │             └─ orchestrator
        │                   ├─ asr.engine      (torch, transformers, qwen_asr)
        │                   ├─ translation.engine (torch, transformers, opencc)
        │                   └─ diarization, media, subtitles, ...
        │
        ├─ [F] SubtitleGeneratorWindow.__init__
        │     ├─ torch.cuda.is_available()     (CUDA probe)
        │     ├─ torch.cuda.get_device_name() (if CUDA)
        │     └─ subprocess: ffmpeg -version   (second ffmpeg check)
        │
        └─ [G] window.show()  ← user finally sees the GUI
```

### 16.2 Root causes (ranked by impact)

| # | Cause | Where | Why it is slow |
|---|-------|-------|----------------|
| 1 | **Duplicate heavy imports** | `run.bat` line 18 + GUI launch | The same ML stack (`torch`, `transformers`, `qwen_asr`, …) is imported **twice** — once for the pre-check, once when the GUI starts |
| 2 | **`import torch` at GUI startup** | `gui.py` line 5, `pipeline_config.py` line 7 | PyTorch loads large native DLLs; with NVIDIA drivers it also initializes CUDA (often 3–15+ seconds) |
| 3 | **Eager pipeline imports in GUI** | `gui.py` lines 31 and 33 → `pipeline_config` / `subtitle_service` → `orchestrator` → `asr.engine` / `translation.engine` | The full subtitle pipeline is pulled in at import time even though processing only starts on button click |
| 4 | **CUDA probes in `__init__`** | `gui.py` lines 116–119, 407–408 | `torch.cuda.is_available()` and `get_device_name(0)` run before the window is shown |
| 5 | **PyInstaller `onedir` + UPX** | `packaging/subtitle_app.spec` | Built `.exe` unpacks/loads many DLLs from `_internal\`; `upx=True` can add extra decompression cost on cold start |
| 6 | **Antivirus scanning** | OS level | First launch of `pythonw` / `.exe` after install may be scanned, adding seconds on some machines |

### 16.3 What is NOT slow at startup

These only run when you click **生成字幕** (not at window open):

- Downloading Hugging Face model weights
- Loading Qwen ASR model into GPU/RAM
- Loading translation model into GPU/RAM
- FFmpeg audio extraction

So a long wait **before the window appears** = import/launcher problem. A long wait **after clicking 生成字幕** = model loading (expected).

### 16.4 Expected rough timings (dev `.bat` launch)

Typical ranges on a GPU machine (not exact benchmarks):

| Phase | Approx. time |
|-------|----------------|
| `run.bat` import pre-check | 5–20 s |
| GUI module import + CUDA init | 5–20 s |
| Window render | < 1 s |
| **Total to visible window** | **10–40 s** |

CPU-only or antivirus-heavy machines can be slower. PyInstaller `.exe` first launch can add more.

### 16.5 Recommended fixes (optional — separate Cursor task)

Implement in this order. Each is independent; together they can cut startup from tens of seconds to a few seconds.

### 16.5.1 Does this also fix the packaged `.exe`?

Partially.

| Fix | Helps `run.bat` dev launch? | Helps packaged `.exe`? | Notes |
|-----|-----------------------------|-------------------------|-------|
| Venv migration | Yes | No direct effect | The `.exe` is already isolated by PyInstaller; it does not use `.venv` at runtime |
| Remove heavy `run.bat` import check | Yes | No | The `.exe` does not run `run.bat` |
| Lazy-import `SubtitleService` / pipeline | Yes | Yes | Reduces Python modules and ML libraries loaded before the GUI appears |
| Remove/defer `torch` from GUI startup path | Yes | Yes | Biggest shared fix for both dev launch and `.exe` launch |
| Defer CUDA device detection | Yes | Yes | Avoids blocking first window paint |
| PyInstaller `upx=False` / packaging tuning | No | Yes | Applies only to the packaged app |

So for the packaged app, the important fixes are:

1. Lazy-import heavy pipeline code.
2. Ensure importing `japanese_subtitle.app.gui` does not import `torch`.
3. Defer GPU/CUDA detection until after the window is visible.
4. Tune the PyInstaller spec if cold start is still slow.

The `.exe` startup can still be slower than `run.bat` because PyInstaller must initialize its bootloader and load many bundled DLLs from `dist\JapaneseSubtitleGenerator\_internal\`. Antivirus scanning can also slow the first launch after build or copy.

#### Fix 1 — Simplify `run.bat` pre-check (high impact, low risk)

**Current:** imports the entire ML stack before launch.

**Change:** after venv migration, only verify the venv exists and the lightweight GUI dependencies are importable:

```bat
"%PY%" -c "import japanese_subtitle, PySide6" >nul 2>&1
```

Do **not** import `torch`, `transformers`, `qwen_asr`, `sklearn`, or `resemblyzer` in `run.bat`.

#### Fix 2 — Lazy-import pipeline code in GUI (high impact, medium risk)

**Current:** `gui.py` line 33 imports `SubtitleService` at module level.

**Change:** move the import inside `SubtitleWorker.run()` and `BurnWorker.run()`:

```python
def run(self):
    from japanese_subtitle.services.subtitle_service import SubtitleService
    ...
```

This prevents `orchestrator` → `asr.engine` → `translation.engine` from loading until the user starts a job.

Also move `PipelineConfig` usage out of the GUI import path. `gui.py` currently imports `PipelineConfig` at module level, and `pipeline_config.py` imports `torch` at module level. That means startup still pays PyTorch import cost even after moving `SubtitleService`.

Use one of these approaches:

- Preferred: remove top-level `import torch` from `pipeline_config.py`; resolve the default device through a small helper that imports `torch` only inside `PipelineConfig.__post_init__`.
- Alternative: move `PipelineConfig` import inside `generate_subtitles()` and avoid using it in top-level type annotations.

Do not instantiate `PipelineConfig` until the user clicks **生成字幕**.

#### Fix 3 — Defer `torch` in GUI (medium impact, medium risk)

**Current:** `import torch` at top of `gui.py` for device labels, and `pipeline_config.py` imports `torch` at top level.

**Change options:**

- Load device info in a background `QThread` after `window.show()`
- Or show "正在检测 GPU…" and update the label when ready
- Keep `torch` out of the critical path to first paint
- Ensure importing `japanese_subtitle.app.gui` does not import `torch`

#### Fix 4 — Defer CUDA probe (low–medium impact, low risk)

**Current:** `torch.cuda.is_available()` in `_build_ui()` blocks window construction.

**Change:** call CUDA checks in `_log_device_info()` only after the window is visible, or from a background thread.

#### Fix 5 — PyInstaller startup tuning (for built `.exe` only)

In `packaging/subtitle_app.spec`:

- Consider `upx=False` for faster cold start (larger disk footprint)
- Ensure build machine matches target GPU/CUDA environment

Also test the built app after code-level startup fixes. If startup is still slow:

- Compare first launch vs second launch; a slow first launch can be Windows Defender / antivirus scanning.
- Keep PyInstaller in `onedir` mode for this project; `onefile` usually makes heavy ML apps start slower because it extracts files before launch.
- Avoid bundling unused heavy libraries where possible, but do this carefully because PyTorch / Transformers often rely on dynamic imports.
- Use `console=True` temporarily in the spec only for debugging startup errors, then switch it back to `False` for release.

### 16.6 Cursor prompt for startup optimization (copy and paste)

Use **after** venv migration is complete:

```
Optimize application startup time as described in docs/VENV_MIGRATION.md Section 16.

Implement Fix 1 through Fix 5 in order:
1. Simplify run.bat pre-check (venv only checks import japanese_subtitle and PySide6, not full ML stack)
2. Lazy-import SubtitleService inside worker run() methods in gui.py
3. Remove torch from the GUI import path:
   - move PipelineConfig import out of top-level gui.py, or
   - remove top-level torch import from pipeline_config.py
4. Defer torch/CUDA device detection until after window.show() (background thread or delayed update)
5. For the packaged .exe, evaluate PyInstaller startup tuning:
   - consider upx=False
   - keep onedir mode
   - do not switch to onefile for this ML-heavy app
6. Keep user-facing messages in Chinese

Do not change model loading behavior during subtitle generation.
Add brief comments only where the deferral logic is non-obvious.
Do not commit unless I ask.
```

### 16.7 How to measure improvement

Before and after changes, time these commands in PowerShell:

```powershell
# Launcher pre-check only (after venv migration)
Measure-Command { .\.venv\Scripts\python.exe -c "import japanese_subtitle, PySide6" }

# Full GUI import (no window)
Measure-Command { .\.venv\Scripts\python.exe -c "import japanese_subtitle.app.gui" }

# End-to-end perceived time: double-click run.bat → window visible (stopwatch)

# Packaged app perceived time: double-click dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe → window visible (stopwatch)
```

Record results in a note; aim for:

- [ ] Pre-check < 2 s
- [ ] GUI import does not import `torch`
- [ ] GUI import < 5 s (GPU machine with deferred torch)
- [ ] Window visible < 3 s after process start
- [ ] Packaged `.exe` second launch is close to dev launch timing; first launch may be slower due to antivirus scanning

---

*Document version: 1.2 — refined venv migration + Python-version policy + startup time analysis.*
