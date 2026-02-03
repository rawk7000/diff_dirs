#!/usr/bin/env python3
"""
diff_dirs – Compare project folders recursively.
Reads all settings from a YAML configuration file.

Usage:
    python diff_dirs.py                     # looks for diff_dirs.yaml in current folder
    python diff_dirs.py my_config.yaml      # specify custom config file
    python diff_dirs.py --init              # generates an example configuration
"""

import os
import sys
import difflib
import hashlib
import fnmatch
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with:")
    print("  pip install pyyaml")
    sys.exit(1)


# ══════════════════════════════════════════════
# ANSI Colors
# ══════════════════════════════════════════════
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def disable():
        for attr in ["RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "CYAN", "BOLD", "DIM", "RESET"]:
            setattr(C, attr, "")


# ══════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════
DEFAULT_CONFIG_NAME = "diff_dirs.yaml"

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg", ".tiff",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar", ".jar", ".war", ".class",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg", ".webm",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".msi",
    ".sqlite", ".db", ".db-journal", ".db-shm", ".db-wal",
    ".pyc", ".pyo", ".o", ".obj", ".a", ".lib",
    ".ico", ".icns", ".cur",
}

LANG_MAP = {
    ".ts": "TypeScript", ".tsx": "React TSX", ".js": "JavaScript", ".jsx": "React JSX",
    ".java": "Java", ".py": "Python", ".css": "CSS", ".scss": "SCSS",
    ".html": "HTML", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".xml": "XML", ".md": "Markdown", ".sql": "SQL", ".sh": "Shell",
    ".env": "Environment", ".properties": "Properties", ".gradle": "Gradle",
    ".toml": "TOML", ".cfg": "Config", ".log": "Log", ".txt": "Text",
    ".ini": "INI", ".conf": "Config", ".bat": "Batch", ".ps1": "PowerShell",
}

INIT_CONFIG = """\
# ┌──────────────────────────────────────────────────────────────┐
# │  diff_dirs - Configuration                                   │
# │  All settings for the project folder comparison              │
# └──────────────────────────────────────────────────────────────┘

# ── Required Fields ──────────────────────────────────────────────
# Paths can be absolute or relative to the config file
original: ./project-original
modified: ./project-modified

# ── Output ────────────────────────────────────────────────────
output:
  # Generate HTML report (false = terminal output only)
  html: true
  # Path to HTML report (relative to config or absolute)
  html_path: ./diff-report.html

  # Colored terminal output
  color: true

  # Show content diffs (false = file list only)
  show_content: true

  # Context lines around each change
  context_lines: 3

# ── Filter ─────────────────────────────────────────────────────
filter:
  # Directories to completely ignore
  ignore_dirs:
    - node_modules
    - .next
    - dist
    - build
    - .git
    - __pycache__
    - .cache
    - .turbo
    - target
    - out
    - .idea
    - .vscode

  # Files/patterns to ignore (glob syntax)
  ignore_files:
    # - "*.log"          # uncomment to ignore log files
    - ".DS_Store"
    - "Thumbs.db"
    - "*.pyc"

  # Only compare specific file types
  # Leave empty or comment out = all file types
  # extensions:
  #   - .ts
  #   - .tsx
  #   - .js
  #   - .jsx
  #   - .java
  #   - .css
"""


# ══════════════════════════════════════════════
# Load Configuration
# ══════════════════════════════════════════════
class Config:
    """Loads and validates the YAML configuration."""

    def __init__(self, config_path: Path):
        self.config_path = config_path.resolve()
        self.config_dir = self.config_path.parent

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            self._error("Config file is empty or invalid.")

        # Required fields
        if "original" not in raw or "modified" not in raw:
            self._error("'original' and 'modified' must be set in the config.")

        self.dir_original = self._resolve_path(raw["original"])
        self.dir_modified = self._resolve_path(raw["modified"])

        # Output
        out = raw.get("output", {}) or {}
        self.html = out.get("html", False)
        self.html_path = self._resolve_path(out.get("html_path", "./diff-report.html"))
        self.color = out.get("color", True)
        self.show_content = out.get("show_content", True)
        self.context_lines = out.get("context_lines", 3)

        # Filter
        flt = raw.get("filter", {}) or {}
        self.ignore_dirs = set(flt.get("ignore_dirs", []))
        self.ignore_files = list(flt.get("ignore_files", []))
        ext_raw = flt.get("extensions", None)
        self.extensions = None
        if ext_raw:
            self.extensions = set(
                e if e.startswith(".") else f".{e}" for e in ext_raw
            )

    def _resolve_path(self, p):
        """Resolve paths relative to the config file."""
        path = Path(p)
        if not path.is_absolute():
            path = self.config_dir / path
        return path.resolve()

    def _error(self, msg):
        print(f"\033[91mConfig Error: {msg}\033[0m")
        sys.exit(1)

    def validate(self):
        if not self.dir_original.exists():
            self._error(f"Original folder does not exist: {self.dir_original}")
        if not self.dir_modified.exists():
            self._error(f"Modified folder does not exist: {self.dir_modified}")
        if not self.dir_original.is_dir():
            self._error(f"Not a folder: {self.dir_original}")
        if not self.dir_modified.is_dir():
            self._error(f"Not a folder: {self.dir_modified}")


# ══════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════
def is_binary(filepath):
    ext = Path(filepath).suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return True
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except (OSError, IOError):
        return True


def file_hash(filepath):
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except (OSError, IOError):
        return None
    return h.hexdigest()


def read_lines(filepath):
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def file_size_human(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_lang(filepath):
    ext = Path(filepath).suffix.lower()
    return LANG_MAP.get(ext, ext.upper().lstrip(".") if ext else "Unknown")


def matches_ignore(filename, patterns):
    """Check if a filename matches an ignore pattern."""
    return any(fnmatch.fnmatch(filename, p) for p in patterns)


def collect_files(base_dir, ignore_dirs, ignore_files, extensions=None):
    """Collect all files recursively considering all filters."""
    result = set()
    base = Path(base_dir).resolve()
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if matches_ignore(f, ignore_files):
                continue
            full = Path(root) / f
            rel = full.relative_to(base)
            if extensions and full.suffix.lower() not in extensions:
                continue
            result.add(str(rel))
    return result


# ══════════════════════════════════════════════
# Diff Result
# ══════════════════════════════════════════════
class FileDiff:
    def __init__(self, rel_path, status, details=None):
        self.rel_path = rel_path
        self.status = status  # added, deleted, modified, binary_modified
        self.details = details or {}
        self.lang = get_lang(rel_path)
        self.lines_added = 0
        self.lines_removed = 0
        self.diff_lines = []


# ══════════════════════════════════════════════
# Main Comparison
# ══════════════════════════════════════════════
def compare_directories(cfg: Config):
    files_a = collect_files(cfg.dir_original, cfg.ignore_dirs, cfg.ignore_files, cfg.extensions)
    files_b = collect_files(cfg.dir_modified, cfg.ignore_dirs, cfg.ignore_files, cfg.extensions)

    only_in_a = files_a - files_b
    only_in_b = files_b - files_a
    common = files_a & files_b

    diffs = []

    # Deleted (only in Original)
    for rel in sorted(only_in_a):
        fp = cfg.dir_original / rel
        d = FileDiff(rel, "deleted", {"size": fp.stat().st_size if fp.exists() else 0})
        diffs.append(d)

    # New (only in Modified)
    for rel in sorted(only_in_b):
        fp = cfg.dir_modified / rel
        d = FileDiff(rel, "added", {"size": fp.stat().st_size if fp.exists() else 0})
        diffs.append(d)

    # Common files
    for rel in sorted(common):
        fp_a = cfg.dir_original / rel
        fp_b = cfg.dir_modified / rel

        if file_hash(fp_a) == file_hash(fp_b):
            continue

        if is_binary(fp_a) or is_binary(fp_b):
            diffs.append(FileDiff(rel, "binary_modified", {
                "size_a": fp_a.stat().st_size,
                "size_b": fp_b.stat().st_size,
            }))
            continue

        lines_a = read_lines(fp_a)
        lines_b = read_lines(fp_b)

        if lines_a is None or lines_b is None:
            diffs.append(FileDiff(rel, "binary_modified", {
                "size_a": fp_a.stat().st_size,
                "size_b": fp_b.stat().st_size,
            }))
            continue

        d = FileDiff(rel, "modified", {
            "size_a": fp_a.stat().st_size,
            "size_b": fp_b.stat().st_size,
        })

        if cfg.show_content:
            unified = list(difflib.unified_diff(
                lines_a, lines_b,
                fromfile=f"original/{rel}",
                tofile=f"modified/{rel}",
                n=cfg.context_lines,
            ))
            d.diff_lines = unified
            d.lines_added = sum(1 for l in unified if l.startswith("+") and not l.startswith("+++"))
            d.lines_removed = sum(1 for l in unified if l.startswith("-") and not l.startswith("---"))

        diffs.append(d)

    return diffs, len(files_a), len(files_b), len(common)


# ══════════════════════════════════════════════
# Terminal Output
# ══════════════════════════════════════════════
def print_report(diffs, total_a, total_b, common, cfg: Config):
    added = [d for d in diffs if d.status == "added"]
    deleted = [d for d in diffs if d.status == "deleted"]
    modified = [d for d in diffs if d.status == "modified"]
    bin_mod = [d for d in diffs if d.status == "binary_modified"]
    unchanged = common - len(modified) - len(bin_mod)

    total_lines_added = sum(d.lines_added for d in diffs)
    total_lines_removed = sum(d.lines_removed for d in diffs)

    lang_stats = defaultdict(lambda: {"added": 0, "deleted": 0, "modified": 0})
    for d in diffs:
        lang_stats[d.lang][d.status if d.status != "binary_modified" else "modified"] += 1

    print()
    print(f"{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"{C.BOLD}  DIRECTORY DIFF REPORT{C.RESET}")
    print(f"{C.BOLD}{'═' * 70}{C.RESET}")
    print(f"  {C.DIM}Original:{C.RESET}  {cfg.dir_original}")
    print(f"  {C.DIM}Modified:{C.RESET}  {cfg.dir_modified}")
    print(f"  {C.DIM}Config:{C.RESET}    {cfg.config_path}")
    print(f"  {C.DIM}Timestamp:{C.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{C.BOLD}{'─' * 70}{C.RESET}")

    print(f"\n  {C.BOLD}OVERVIEW{C.RESET}")
    print(f"  Files in Original:      {total_a}")
    print(f"  Files in Modified:      {total_b}")
    print(f"  Unchanged:              {C.DIM}{unchanged}{C.RESET}")
    print(f"  {C.GREEN}+ New Files:             {len(added)}{C.RESET}")
    print(f"  {C.RED}- Deleted Files:         {len(deleted)}{C.RESET}")
    print(f"  {C.YELLOW}~ Modified Files:        {len(modified)}{C.RESET}")
    print(f"  {C.MAGENTA}~ Binary Modified:       {len(bin_mod)}{C.RESET}")
    print(f"  {C.CYAN}Lines Added:             +{total_lines_added}{C.RESET}")
    print(f"  {C.RED}Lines Removed:           -{total_lines_removed}{C.RESET}")

    if lang_stats:
        print(f"\n  {C.BOLD}BY FILE TYPE{C.RESET}")
        for lang in sorted(lang_stats):
            s = lang_stats[lang]
            parts = []
            if s["added"]:   parts.append(f"{C.GREEN}+{s['added']}{C.RESET}")
            if s["deleted"]: parts.append(f"{C.RED}-{s['deleted']}{C.RESET}")
            if s["modified"]:parts.append(f"{C.YELLOW}~{s['modified']}{C.RESET}")
            print(f"    {lang:<20s} {' '.join(parts)}")

    if added:
        print(f"\n{C.BOLD}{'─' * 70}{C.RESET}")
        print(f"  {C.GREEN}{C.BOLD}NEW FILES ({len(added)}){C.RESET}")
        for d in sorted(added, key=lambda x: x.rel_path):
            size = file_size_human(d.details.get("size", 0))
            print(f"    {C.GREEN}+ {d.rel_path}{C.RESET}  {C.DIM}({size}){C.RESET}")

    if deleted:
        print(f"\n{C.BOLD}{'─' * 70}{C.RESET}")
        print(f"  {C.RED}{C.BOLD}DELETED FILES ({len(deleted)}){C.RESET}")
        for d in sorted(deleted, key=lambda x: x.rel_path):
            size = file_size_human(d.details.get("size", 0))
            print(f"    {C.RED}- {d.rel_path}{C.RESET}  {C.DIM}({size}){C.RESET}")

    if bin_mod:
        print(f"\n{C.BOLD}{'─' * 70}{C.RESET}")
        print(f"  {C.MAGENTA}{C.BOLD}BINARY MODIFIED ({len(bin_mod)}){C.RESET}")
        for d in sorted(bin_mod, key=lambda x: x.rel_path):
            sa = file_size_human(d.details.get("size_a", 0))
            sb = file_size_human(d.details.get("size_b", 0))
            print(f"    {C.MAGENTA}~ {d.rel_path}{C.RESET}  {C.DIM}({sa} → {sb}){C.RESET}")

    if modified:
        print(f"\n{C.BOLD}{'─' * 70}{C.RESET}")
        print(f"  {C.YELLOW}{C.BOLD}MODIFIED FILES ({len(modified)}){C.RESET}")

        for d in sorted(modified, key=lambda x: x.rel_path):
            sa = file_size_human(d.details.get("size_a", 0))
            sb = file_size_human(d.details.get("size_b", 0))
            print(f"\n    {C.YELLOW}{C.BOLD}~ {d.rel_path}{C.RESET}  "
                  f"{C.DIM}({sa} → {sb}){C.RESET}  "
                  f"{C.GREEN}+{d.lines_added}{C.RESET} {C.RED}-{d.lines_removed}{C.RESET}")

            if d.diff_lines:
                print(f"    {C.DIM}{'·' * 60}{C.RESET}")
                for line in d.diff_lines:
                    line = line.rstrip("\n")
                    if line.startswith("+++") or line.startswith("---"):
                        print(f"      {C.BOLD}{line}{C.RESET}")
                    elif line.startswith("@@"):
                        print(f"      {C.CYAN}{line}{C.RESET}")
                    elif line.startswith("+"):
                        print(f"      {C.GREEN}{line}{C.RESET}")
                    elif line.startswith("-"):
                        print(f"      {C.RED}{line}{C.RESET}")
                    else:
                        print(f"      {C.DIM}{line}{C.RESET}")

    if not diffs:
        print(f"\n  {C.GREEN}{C.BOLD}✓ No differences found! The folders are identical.{C.RESET}")

    print(f"\n{C.BOLD}{'═' * 70}{C.RESET}\n")


# ══════════════════════════════════════════════
# HTML Report
# ══════════════════════════════════════════════
def generate_html_report(diffs, total_a, total_b, common, cfg: Config):
    added = [d for d in diffs if d.status == "added"]
    deleted = [d for d in diffs if d.status == "deleted"]
    modified = [d for d in diffs if d.status == "modified"]
    bin_mod = [d for d in diffs if d.status == "binary_modified"]
    unchanged = common - len(modified) - len(bin_mod)
    total_added = sum(d.lines_added for d in diffs)
    total_removed = sum(d.lines_removed for d in diffs)

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    diff_sections = []
    for d in sorted(modified, key=lambda x: x.rel_path):
        lines_html = []
        for line in d.diff_lines:
            line = line.rstrip("\n")
            escaped = esc(line)
            if line.startswith("+++") or line.startswith("---"):
                lines_html.append(f'<div class="diff-header">{escaped}</div>')
            elif line.startswith("@@"):
                lines_html.append(f'<div class="diff-hunk">{escaped}</div>')
            elif line.startswith("+"):
                lines_html.append(f'<div class="diff-add">{escaped}</div>')
            elif line.startswith("-"):
                lines_html.append(f'<div class="diff-del">{escaped}</div>')
            else:
                lines_html.append(f'<div class="diff-ctx">{escaped}</div>')
        diff_sections.append(f"""
        <details class="file-diff" id="{esc(d.rel_path)}">
            <summary>
                <span class="status mod">~</span>
                <span class="filepath">{esc(d.rel_path)}</span>
                <span class="lang">{esc(d.lang)}</span>
                <span class="stats"><span class="add">+{d.lines_added}</span> <span class="del">-{d.lines_removed}</span></span>
            </summary>
            <div class="diff-content">{''.join(lines_html)}</div>
        </details>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Diff Report – {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
<style>
    :root {{ --bg: #0d1117; --fg: #c9d1d9; --border: #30363d; --green: #3fb950;
             --red: #f85149; --yellow: #d29922; --blue: #58a6ff; --magenta: #bc8cff;
             --surface: #161b22; --diff-add-bg: #12261e; --diff-del-bg: #2d1214; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
            color: var(--fg); padding: 2rem; line-height: 1.6; }}
    h1 {{ color: var(--blue); margin-bottom: 0.5rem; font-size: 1.5rem; }}
    .meta {{ color: #8b949e; margin-bottom: 2rem; font-size: 0.9rem; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                gap: 1rem; margin-bottom: 2rem; }}
    .stat-card {{ background: var(--surface); border: 1px solid var(--border);
                  border-radius: 8px; padding: 1rem; text-align: center; }}
    .stat-card .number {{ font-size: 1.8rem; font-weight: 700; }}
    .stat-card .label {{ font-size: 0.85rem; color: #8b949e; }}
    .section-title {{ font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 0.5rem;
                      padding: 0.5rem 0; border-bottom: 1px solid var(--border); }}
    .file-list {{ list-style: none; }}
    .file-list li {{ padding: 0.3rem 0.5rem; font-family: monospace; font-size: 0.9rem; }}
    .file-list li:hover {{ background: var(--surface); border-radius: 4px; }}
    .file-diff {{ margin: 0.5rem 0; border: 1px solid var(--border); border-radius: 8px;
                  overflow: hidden; }}
    .file-diff summary {{ cursor: pointer; padding: 0.6rem 1rem; background: var(--surface);
                          display: flex; align-items: center; gap: 0.8rem; font-family: monospace;
                          font-size: 0.9rem; }}
    .file-diff summary:hover {{ background: #1c2129; }}
    .status {{ font-weight: 700; width: 1.2rem; text-align: center; }}
    .status.add {{ color: var(--green); }}
    .status.del {{ color: var(--red); }}
    .status.mod {{ color: var(--yellow); }}
    .status.bin {{ color: var(--magenta); }}
    .filepath {{ flex: 1; }}
    .lang {{ color: #8b949e; font-size: 0.8rem; }}
    .stats .add {{ color: var(--green); }}
    .stats .del {{ color: var(--red); margin-left: 0.4rem; }}
    .diff-content {{ font-family: 'Fira Code', 'Consolas', monospace; font-size: 0.82rem;
                     overflow-x: auto; max-height: 600px; overflow-y: auto; }}
    .diff-header {{ padding: 2px 12px; font-weight: 600; background: #1c2129; }}
    .diff-hunk {{ padding: 2px 12px; color: var(--blue); background: #161b22; }}
    .diff-add {{ padding: 2px 12px; background: var(--diff-add-bg); color: var(--green); }}
    .diff-del {{ padding: 2px 12px; background: var(--diff-del-bg); color: var(--red); }}
    .diff-ctx {{ padding: 2px 12px; color: #8b949e; }}
    .filter {{ margin-bottom: 1.5rem; }}
    .filter input {{ background: var(--surface); border: 1px solid var(--border); color: var(--fg);
                     padding: 0.5rem 1rem; border-radius: 6px; width: 100%; max-width: 400px;
                     font-size: 0.9rem; }}
    .filter input::placeholder {{ color: #484f58; }}
    .hidden {{ display: none !important; }}
</style>
</head>
<body>
<h1>📂 Directory Diff Report</h1>
<div class="meta">
    Original: <strong>{esc(str(cfg.dir_original))}</strong><br>
    Modified: <strong>{esc(str(cfg.dir_modified))}</strong><br>
    Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>

<div class="summary">
    <div class="stat-card"><div class="number" style="color:var(--green)">{len(added)}</div><div class="label">New Files</div></div>
    <div class="stat-card"><div class="number" style="color:var(--red)">{len(deleted)}</div><div class="label">Deleted</div></div>
    <div class="stat-card"><div class="number" style="color:var(--yellow)">{len(modified)}</div><div class="label">Modified</div></div>
    <div class="stat-card"><div class="number" style="color:var(--magenta)">{len(bin_mod)}</div><div class="label">Binary Modified</div></div>
    <div class="stat-card"><div class="number">+{total_added}</div><div class="label">Lines Added</div></div>
    <div class="stat-card"><div class="number" style="color:var(--red)">-{total_removed}</div><div class="label">Lines Removed</div></div>
    <div class="stat-card"><div class="number" style="color:#8b949e">{unchanged}</div><div class="label">Unchanged</div></div>
</div>

<div class="filter"><input type="text" id="searchBox" placeholder="🔍 Filter filenames..." oninput="filterFiles()"></div>

{'<div class="section-title" style="color:var(--green)">+ New Files (' + str(len(added)) + ')</div><ul class="file-list">' + ''.join(f'<li class="filterable" data-name="{esc(d.rel_path)}"><span class="status add">+</span> {esc(d.rel_path)} <span class="lang">({file_size_human(d.details.get("size",0))})</span></li>' for d in sorted(added, key=lambda x: x.rel_path)) + '</ul>' if added else ''}

{'<div class="section-title" style="color:var(--red)">- Deleted Files (' + str(len(deleted)) + ')</div><ul class="file-list">' + ''.join(f'<li class="filterable" data-name="{esc(d.rel_path)}"><span class="status del">-</span> {esc(d.rel_path)} <span class="lang">({file_size_human(d.details.get("size",0))})</span></li>' for d in sorted(deleted, key=lambda x: x.rel_path)) + '</ul>' if deleted else ''}

{'<div class="section-title" style="color:var(--magenta)">~ Binary Modified (' + str(len(bin_mod)) + ')</div><ul class="file-list">' + ''.join(f'<li class="filterable" data-name="{esc(d.rel_path)}"><span class="status bin">~</span> {esc(d.rel_path)} <span class="lang">({file_size_human(d.details.get("size_a",0))} → {file_size_human(d.details.get("size_b",0))})</span></li>' for d in sorted(bin_mod, key=lambda x: x.rel_path)) + '</ul>' if bin_mod else ''}

{'<div class="section-title" style="color:var(--yellow)">~ Modified Files (' + str(len(modified)) + ')</div>' + ''.join(diff_sections) if modified else ''}

<script>
function filterFiles() {{
    const q = document.getElementById('searchBox').value.toLowerCase();
    document.querySelectorAll('.filterable, .file-diff').forEach(el => {{
        const name = (el.dataset.name || el.id || '').toLowerCase();
        el.classList.toggle('hidden', q && !name.includes(q));
    }});
}}
</script>
</body>
</html>"""

    cfg.html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg.html_path, "w", encoding="utf-8") as f:
        f.write(html)


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════
def main():
    # --init: Generate example config
    if "--init" in sys.argv:
        target = Path(DEFAULT_CONFIG_NAME)
        if target.exists():
            print(f"{C.YELLOW}'{DEFAULT_CONFIG_NAME}' already exists. Overwrite? [y/N]{C.RESET} ", end="")
            if input().strip().lower() not in ("j", "y", "ja", "yes"):
                print("Cancelled.")
                sys.exit(0)
        with open(target, "w", encoding="utf-8") as f:
            f.write(INIT_CONFIG)
        print(f"{C.GREEN}✓ '{DEFAULT_CONFIG_NAME}' created.{C.RESET}")
        print(f"  Adjust the paths and then run: python diff_dirs.py")
        sys.exit(0)

    # Find config file
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        config_path = Path(sys.argv[1])
    else:
        config_path = Path(DEFAULT_CONFIG_NAME)

    if not config_path.exists():
        print(f"{C.RED}Config file '{config_path}' not found.{C.RESET}")
        print(f"  Create one with:  python diff_dirs.py --init")
        print(f"  Or specify one:   python diff_dirs.py my_config.yaml")
        sys.exit(1)

    # Load & Validate
    cfg = Config(config_path)
    if not cfg.color:
        C.disable()
    cfg.validate()

    # Execute
    print(f"\n{C.CYAN}Comparing folders...{C.RESET}")
    print(f"  {C.DIM}Config:     {cfg.config_path}{C.RESET}")
    print(f"  {C.DIM}Ignoring:   {', '.join(sorted(cfg.ignore_dirs))}{C.RESET}")
    if cfg.ignore_files:
        print(f"  {C.DIM}Ign. Files: {', '.join(cfg.ignore_files)}{C.RESET}")
    if cfg.extensions:
        print(f"  {C.DIM}File Types: {', '.join(sorted(cfg.extensions))}{C.RESET}")

    diffs, total_a, total_b, common = compare_directories(cfg)

    print_report(diffs, total_a, total_b, common, cfg)

    if cfg.html:
        generate_html_report(diffs, total_a, total_b, common, cfg)
        print(f"{C.GREEN}✓ HTML Report: {cfg.html_path}{C.RESET}\n")


if __name__ == "__main__":
    main()
