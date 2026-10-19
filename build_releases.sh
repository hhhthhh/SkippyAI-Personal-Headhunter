#!/bin/bash
set -e

# Ensure script runs from the repository root directory
cd "$(dirname "$0")"

echo "======================================================="
echo "        🦘 Skippy Release Packaging System             "
echo "======================================================="
echo ""

# 1. Pre-flight check: Verify 'zip' or 'python3' is available
USE_PYTHON_ZIP=0
if ! command -v zip &>/dev/null; then
    if command -v python3 &>/dev/null; then
        USE_PYTHON_ZIP=1
    else
        echo "❌ [Error] Neither 'zip' nor 'python3' is installed on this system."
        exit 1
    fi
fi

create_zip() {
    local target_zip="$1"
    shift
    if [ "$USE_PYTHON_ZIP" -eq 0 ]; then
        zip -rq "$target_zip" "$@" "${EXCLUDES[@]}"
    else
        python3 - "$target_zip" "$@" <<'PYEOF'
import os, sys, zipfile

target_zip = sys.argv[1]
items = sys.argv[2:]
exclude_names = {"__pycache__", ".DS_Store", ".env", ".env.local", "skippy.db", "skippy.db-journal", "skippy.db-wal", "resume.md", "inbox.json", "test_venv", "venv", ".venv", ".git"}

with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
    for item in items:
        item_clean = item.rstrip("/")
        if os.path.isdir(item_clean):
            zf.write(item_clean, item_clean + "/")
            for root, dirs, files in os.walk(item_clean):
                dirs[:] = [d for d in dirs if d not in exclude_names]
                for d in dirs:
                    dpath = os.path.join(root, d)
                    zf.write(dpath, dpath + "/")
                for f in files:
                    if f in exclude_names or f.endswith((".pyc", ".pyo", ".pyd", ".db")) or ".DS_Store" in f:
                        continue
                    fpath = os.path.join(root, f)
                    zf.write(fpath, fpath)
        elif os.path.exists(item_clean):
            zf.write(item_clean, item_clean)
PYEOF
    fi
}

verify_zip() {
    local pkg="$1"
    if [ "$USE_PYTHON_ZIP" -eq 0 ] && command -v unzip &>/dev/null; then
        unzip -tq "$pkg" >/dev/null 2>&1
    else
        python3 -c 'import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); sys.exit(0 if z.testzip() is None else 1)' "$pkg"
    fi
}

# 2. Set executable permissions on launcher scripts before packaging
echo "⚙️  Setting executable permissions on launcher scripts..."
chmod +x skippy.sh skippy.command Skippy-LinuxOrMac-Docker-Launch.sh build_releases.sh 2>/dev/null || true

# 3. Create dedicated release output folder and clean stale archives
mkdir -p releases
rm -f releases/*.zip 2>/dev/null || true

# 4. Package latest browser extension bundle
echo "📦 Packaging Chrome/Chromium extension..."
if [ -d "skippy-extension" ]; then
    rm -f skippy_extension.zip 2>/dev/null || true
    EXT_VER=$(python3 -c 'import json; print(json.load(open("skippy-extension/manifest.json")).get("version", "unknown"))' 2>/dev/null || echo "unknown")
    create_zip skippy_extension.zip skippy-extension/
    echo "   ✅ skippy_extension.zip updated (v${EXT_VER})"
else
    echo "⚠️  [Warning] skippy-extension/ directory not found!"
fi

# 5. Core application files required for all target platforms
# Includes all application logic (including pipeline.py), prompts, configuration templates, and pages.
COMMON_FILES="app.py database.py evaluator.py pipeline.py scraper.py utils.py webhook.py requirements.txt custom_prompt.txt prompt_presets.json README.md .env.example skippy_extension.zip skippy-extension/ pages/"

# 6. Pre-flight check: Verify all required core files exist
echo "🔍 Verifying required application files..."
MISSING_FILES=0
for item in $COMMON_FILES; do
    if [ ! -e "$item" ]; then
        echo "   ❌ Missing required file or directory: $item"
        MISSING_FILES=1
    fi
done

if [ "$MISSING_FILES" -ne 0 ]; then
    echo "❌ Release build aborted due to missing core files."
    exit 1
fi
echo "   ✅ All core files verified."

# Common exclusion patterns to guarantee zero data leaks (no personal keys, databases, or resumes)
EXCLUDES=(
    -x "*/__pycache__/*"
    -x "*__pycache__*"
    -x "*.py[cod]"
    -x "*.DS_Store*"
    -x ".DS_Store"
    -x ".env"
    -x ".env.local"
    -x "skippy.db"
    -x "skippy.db-journal"
    -x "skippy.db-wal"
    -x "skippy.db-shm"
    -x "*.db"
    -x "*.db-journal"
    -x "*.db-wal"
    -x "*.db-shm"
    -x "*.sqlite*"
    -x "resume.md"
    -x "*.docx"
    -x "*.pdf"
    -x "inbox.json"
    -x "*.tmp"
    -x "*.temp"
    -x "*.bak"
    -x "*.swp"
    -x "*.log"
    -x "test_venv/*"
    -x "venv/*"
    -x ".venv/*"
    -x ".git/*"
)

# 7. Package 1: Windows (Native Portable Installer)
echo ""
echo "🚀 [1/3] Building Skippy-Windows.zip..."
create_zip releases/Skippy-Windows.zip $COMMON_FILES skippy.bat
echo "   ✅ Skippy-Windows.zip created ($(du -h releases/Skippy-Windows.zip 2>/dev/null | cut -f1))"

# 8. Package 2: Unix / Mac & Linux (Native One-Click Launchers)
echo ""
echo "🚀 [2/3] Building Skippy-Unix.zip..."
create_zip releases/Skippy-Unix.zip $COMMON_FILES skippy.sh skippy.command
echo "   ✅ Skippy-Unix.zip created ($(du -h releases/Skippy-Unix.zip 2>/dev/null | cut -f1))"

# 9. Package 3: Docker (Cross-Platform Container Deployment)
echo ""
echo "🚀 [3/3] Building Skippy-Docker.zip..."
create_zip releases/Skippy-Docker.zip $COMMON_FILES dockerfile docker-compose.yml .dockerignore Skippy-Docker-Windows.bat Skippy-LinuxOrMac-Docker-Launch.sh
echo "   ✅ Skippy-Docker.zip created ($(du -h releases/Skippy-Docker.zip 2>/dev/null | cut -f1))"

# 10. Verification of built archives
echo ""
echo "🔍 Validating archive integrity..."
for pkg in releases/*.zip; do
    if [ -f "$pkg" ]; then
        if verify_zip "$pkg"; then
            echo "   ✅ Integrity OK: $(basename "$pkg")"
        else
            echo "   ❌ Corrupt archive detected: $(basename "$pkg")"
            exit 1
        fi
    fi
done

echo ""
echo "======================================================="
echo " 🎉 All release packages successfully built in 'releases/'"
echo "======================================================="
ls -lh releases/*.zip