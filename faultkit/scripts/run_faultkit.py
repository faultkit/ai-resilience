#!/usr/bin/env python3
"""Acquire faultkit, run one scenario against a target command, evaluate the proof.

Standard library only. Prints a proof block on stdout and exits with faultkit's
own exit code so shells and CI can branch on it:

    0  invariant proven under fault (faults fired > 0, target passed)
    1  silent failure confirmed     (faults fired > 0, target failed)
    2  faultkit internal error
    3  invalid evidence             (no fault fired; the target never reached faultkit)
    4  usage error

Binary resolution, first match wins: --faultkit-bin, $FAULTKIT, faultkit on
PATH, --faultkit-source (go build), then a checksum-verified download of the
pinned release into the cache directory.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable, Optional

# Bumped deliberately, never resolved from "latest". faultkit's own supply-chain
# rule asks for roughly ten days of cooldown before adopting a new release.
PINNED_VERSION = "v0.1.2"
RELEASES_URL = "https://github.com/faultkit/faultkit/releases/download"
DEFAULT_CACHE = Path.home() / ".cache" / "faultkit"

PLATFORMS = {
    ("linux", "x86_64"): ("linux", "amd64"),
    ("linux", "amd64"): ("linux", "amd64"),
    ("linux", "aarch64"): ("linux", "arm64"),
    ("linux", "arm64"): ("linux", "arm64"),
    ("darwin", "x86_64"): ("darwin", "amd64"),
    ("darwin", "arm64"): ("darwin", "arm64"),
}

EXIT_OK, EXIT_TARGET_FAILED, EXIT_INTERNAL, EXIT_FAULT_NOT_FIRED, EXIT_USAGE = 0, 1, 2, 3, 4

ANSI = {"reset": "\033[0m", "bold": "\033[1m", "green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m", "magenta": "\033[35m"}
STATE_COLOR = [
    ("invariant proven under fault", "green"),
    ("silent failure confirmed", "red"),
    ("invalid evidence", "yellow"),
    ("error", "magenta"),
]


class UnsupportedPlatform(Exception):
    """No faultkit release exists for this operating system and architecture."""


class ChecksumMismatch(Exception):
    """The downloaded archive does not match the release's checksums.txt."""


def platform_key(system: Optional[str] = None, machine: Optional[str] = None) -> tuple[str, str]:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    try:
        return PLATFORMS[(system, machine)]
    except KeyError:
        supported = ", ".join(sorted({f"{o}/{a}" for o, a in PLATFORMS.values()}))
        raise UnsupportedPlatform(
            f"{system}/{machine} has no faultkit release; supported: {supported}"
        ) from None


def asset_name(version: str, os_name: str, arch: str) -> str:
    return f"faultkit_{version.lstrip('v')}_{os_name}_{arch}.tar.gz"


def verify_checksum(data: bytes, checksums_txt: str, name: str) -> None:
    expected = None
    for line in checksums_txt.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == name:
            expected = parts[0]
    actual = hashlib.sha256(data).hexdigest()
    if expected is None:
        raise ChecksumMismatch(f"{name} is not listed in checksums.txt (actual sha256 {actual})")
    if expected != actual:
        raise ChecksumMismatch(f"sha256 mismatch for {name}: expected {expected}, actual {actual}")


def _fetch(url: str) -> bytes:
    # The host is fixed to GitHub releases and the version is pinned; nothing
    # user-controlled reaches this URL.
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read()


def download(version: str, cache_dir: Path) -> Path:
    os_name, arch = platform_key()
    target = cache_dir / version / "faultkit"
    if target.exists():
        return target
    name = asset_name(version, os_name, arch)
    base = f"{RELEASES_URL}/{version}"
    archive = _fetch(f"{base}/{name}")
    verify_checksum(archive, _fetch(f"{base}/checksums.txt").decode(), name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        member = next(m for m in tar.getmembers() if m.isfile() and m.name.rstrip("/").endswith("faultkit"))
        source = tar.extractfile(member)
        if source is None:
            raise ChecksumMismatch(f"{name} contains no faultkit binary")
        with source, target.open("wb") as dst:
            shutil.copyfileobj(source, dst)
    target.chmod(0o755)
    return target


def build_from_source(source: Path, cache_dir: Path) -> Path:
    target = cache_dir / "source-build" / "faultkit"
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["go", "build", "-mod=vendor", "-o", str(target), "./cmd/faultkit"],
        cwd=source,
        check=True,
    )
    return target


def resolve_binary(
    explicit: Optional[str],
    env: dict,
    which: Callable[[str], Optional[str]],
    source: Optional[str],
    cache_dir: Path,
    version: str,
    downloader: Callable[[str, Path], Path],
) -> Path:
    if explicit:
        return Path(explicit)
    if env.get("FAULTKIT"):
        return Path(env["FAULTKIT"])
    found = which("faultkit")
    if found:
        return Path(found)
    if source:
        return build_from_source(Path(source), cache_dir)
    return downloader(version, cache_dir)


def fired_count(report: dict) -> int:
    return sum(1 for event in report.get("events") or [] if event.get("fired"))


def proof_state(exit_code: int, fired: int) -> str:
    nothing_injected = exit_code == EXIT_FAULT_NOT_FIRED or (
        fired == 0 and exit_code in (EXIT_OK, EXIT_TARGET_FAILED)
    )
    if nothing_injected:
        return "invalid evidence: nothing was injected"
    if exit_code == EXIT_TARGET_FAILED:
        return "silent failure confirmed"
    if exit_code == EXIT_OK:
        return "invariant proven under fault"
    return f"error: faultkit exited {exit_code}"


def use_color(mode: str, isatty: bool, env: dict) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if env.get("NO_COLOR"):
        return False
    if env.get("FORCE_COLOR"):
        return True
    return isatty


def paint(text: str, color: str, enabled: bool) -> str:
    return f"{ANSI[color]}{text}{ANSI['reset']}" if enabled else text


def render_proof(scenario: str, mode: str, fired: int, exit_code: int, state: str, report: str, color: bool) -> str:
    state_color = next(c for prefix, c in STATE_COLOR if state.startswith(prefix))
    return "\n".join(
        [
            paint("=== proof ===", "bold", color),
            f"scenario:      {scenario}",
            f"mode:          {mode}",
            f"faults fired:  {paint(str(fired), 'green' if fired else 'yellow', color)}",
            f"target exit:   {exit_code}",
            f"proof state:   {paint(state, state_color, color)}",
            f"report:        {report}",
        ]
    )


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    if "--" in argv:
        split = argv.index("--")
        own, target = argv[:split], argv[split + 1:]
    else:
        own, target = argv, []
    parser = argparse.ArgumentParser(
        prog="run_faultkit.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", required=True, help="scenario YAML file")
    parser.add_argument("--report", required=True, help="where faultkit writes its JSON report")
    parser.add_argument("--faultkit-bin", help="explicit faultkit binary")
    parser.add_argument("--faultkit-source", help="faultkit source tree to build with go")
    parser.add_argument(
        "--faultkit-version", default=PINNED_VERSION,
        help=f"release to download when nothing else resolves (default {PINNED_VERSION})",
    )
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument(
        "--base-url", action="store_true",
        help="inject *_BASE_URL instead of HTTPS_PROXY (Node fetch, filtered subprocesses)",
    )
    parser.add_argument("--provider", help="limit failure modes to one provider")
    parser.add_argument("--mode", default="auto", choices=["auto", "proxy", "ebpf"])
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--color", default="auto", choices=["auto", "always", "never"],
        help="colour the proof block (auto: when stdout is a terminal; NO_COLOR and FORCE_COLOR are honoured)",
    )
    ns = parser.parse_args(own)
    if not target:
        parser.error("missing target command after --")
    return ns, target


def main(argv: Optional[list[str]] = None) -> int:
    ns, target = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        binary = resolve_binary(
            ns.faultkit_bin, dict(os.environ), shutil.which, ns.faultkit_source,
            Path(ns.cache_dir), ns.faultkit_version, download,
        )
    except (UnsupportedPlatform, ChecksumMismatch, subprocess.CalledProcessError, OSError) as exc:
        print(f"error: could not obtain faultkit: {exc}", file=sys.stderr)
        return EXIT_INTERNAL

    command = [str(binary), "run", "--config", ns.config, "--report", ns.report, "--mode", ns.mode]
    if ns.base_url:
        command.append("--base-url")
    if ns.provider:
        command += ["--provider", ns.provider]
    if ns.verbose:
        command.append("--verbose")
    command += ["--", *target]

    completed = subprocess.run(command)
    fired = 0
    try:
        with open(ns.report, encoding="utf-8") as handle:
            fired = fired_count(json.load(handle))
    except (OSError, ValueError):
        pass

    color = use_color(ns.color, sys.stdout.isatty(), dict(os.environ))
    print(render_proof(
        ns.config, "base-url" if ns.base_url else ns.mode, fired, completed.returncode,
        proof_state(completed.returncode, fired), ns.report, color,
    ), flush=True)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
