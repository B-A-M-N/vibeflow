#!/usr/bin/env python3
"""Install/sync VibeFlow into multiple Claude Code config profiles.

This is intentionally explicit. Claude Code plugin installation is scoped to a
single config root, so alternate homes such as ~/.claude-openrouter-1 need their
own local marketplace/plugin copy.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_NAME = "vibe-flow"
MARKETPLACE_NAME = "local"
COPY_ITEMS = [
    ".claude-plugin",
    "commands",
    "skills",
    "references",
    "scripts",
    "examples",
    "README.md",
    "LICENSE",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any, apply: bool) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def looks_like_claude_profile(path: Path) -> bool:
    if not path.is_dir():
        return False
    markers = [
        path / "settings.json",
        path / "plugins",
        path / "projects",
        path / "sessions",
    ]
    return any(marker.exists() for marker in markers)


def discover_profiles(home: Path) -> list[Path]:
    candidates = [home / ".claude"]
    candidates.extend(sorted(home.glob(".claude-openrouter*")))
    profiles: list[Path] = []
    for candidate in candidates:
        if candidate not in profiles and looks_like_claude_profile(candidate):
            profiles.append(candidate)
    return profiles


def sync_plugin_files(src: Path, dst: Path, apply: bool) -> None:
    if not apply:
        return
    if dst.exists() or dst.is_symlink():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for item in COPY_ITEMS:
        source = src / item
        target = dst / item
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif source.exists():
            shutil.copy2(source, target)


def update_marketplace(profile: Path, plugin_dst: Path, apply: bool) -> None:
    local = profile / "plugins" / "marketplaces" / MARKETPLACE_NAME
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    modern_path = local / ".claude-plugin" / "marketplace.json"
    modern = read_json(modern_path, {})
    modern.setdefault("$schema", "https://anthropic.com/claude-code/marketplace.schema.json")
    modern["name"] = MARKETPLACE_NAME
    modern.setdefault("description", "Local plugins for personal use")
    modern.setdefault("owner", {"name": os.environ.get("USER", "local")})
    plugins = modern.get("plugins") if isinstance(modern.get("plugins"), list) else []
    plugins = [p for p in plugins if p.get("name") != PLUGIN_NAME]
    plugins.append(
        {
            "name": PLUGIN_NAME,
            "description": "Single-model Claude Code lifecycle for designing, planning, applying, and validating Mistral Vibe workflows",
            "source": "./plugins/vibe-flow",
            "category": "productivity",
        }
    )
    modern["plugins"] = plugins
    write_json(modern_path, modern, apply)

    legacy_path = local / "marketplace.json"
    legacy = read_json(legacy_path, {})
    legacy["name"] = MARKETPLACE_NAME
    legacy.setdefault("displayName", "Local Plugins")
    legacy.setdefault("description", "User's local plugin directory")
    legacy_plugins = legacy.get("plugins") if isinstance(legacy.get("plugins"), dict) else {}
    legacy_plugins[PLUGIN_NAME] = {
        "source": "./plugins/vibe-flow",
        "version": "1.0.0",
        "description": "Single-model Claude Code lifecycle for Mistral Vibe workflows",
    }
    legacy["plugins"] = legacy_plugins
    write_json(legacy_path, legacy, apply)

    known_path = profile / "plugins" / "known_marketplaces.json"
    known = read_json(known_path, {})
    known[MARKETPLACE_NAME] = {
        "source": {"source": "directory", "path": str(local)},
        "installLocation": str(local),
        "lastUpdated": now,
    }
    write_json(known_path, known, apply)


def update_settings(profile: Path, plugin_dst: Path, apply: bool) -> None:
    settings_path = profile / "settings.json"
    settings = read_json(settings_path, {})
    enabled = settings.get("enabledPlugins") if isinstance(settings.get("enabledPlugins"), dict) else {}
    enabled[f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"] = True
    settings["enabledPlugins"] = enabled

    # Older/local wrappers in this environment also honor this map.
    plugins = settings.get("plugins") if isinstance(settings.get("plugins"), dict) else {}
    plugins[PLUGIN_NAME] = {"source": str(plugin_dst)}
    settings["plugins"] = plugins

    write_json(settings_path, settings, apply)


def run_claude_update(profile: Path, apply: bool, install_cache: bool) -> None:
    if not apply or not install_cache:
        return
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(profile)
    update = subprocess.run(
        ["claude", "plugin", "update", f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if update.returncode == 0:
        print(update.stdout.strip())
        return
    install = subprocess.run(
        ["claude", "plugin", "install", f"{PLUGIN_NAME}@{MARKETPLACE_NAME}", "--scope", "user"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print((install.stdout or update.stdout).strip())
    if install.returncode != 0:
        raise SystemExit(f"Claude plugin install/update failed for {profile}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync VibeFlow into ~/.claude and ~/.claude-openrouter* profiles.",
    )
    parser.add_argument("--apply", action="store_true", help="write changes")
    parser.add_argument(
        "--install-cache",
        action="store_true",
        help="also run claude plugin update/install for each profile",
    )
    parser.add_argument(
        "--profile",
        action="append",
        type=Path,
        help="specific Claude config profile root; may be repeated",
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()

    src = repo_root()
    profiles = [p.expanduser().resolve() for p in args.profile] if args.profile else discover_profiles(args.home)
    if not profiles:
        raise SystemExit("No Claude profiles found.")

    for profile in profiles:
        if not looks_like_claude_profile(profile):
            print(f"skip {profile}: does not look like a Claude profile")
            continue
        plugin_dst = profile / "plugins" / "marketplaces" / MARKETPLACE_NAME / "plugins" / PLUGIN_NAME
        print(f"{'sync' if args.apply else 'would sync'} {src} -> {plugin_dst}")
        sync_plugin_files(src, plugin_dst, args.apply)
        update_marketplace(profile, plugin_dst, args.apply)
        update_settings(profile, plugin_dst, args.apply)
        run_claude_update(profile, args.apply, args.install_cache)

    if not args.apply:
        print("dry run only; rerun with --apply to write changes")


if __name__ == "__main__":
    main()
