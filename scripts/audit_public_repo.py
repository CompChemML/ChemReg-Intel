"""Fail when the public Git index contains likely private data or secrets."""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SUFFIXES = {".docx", ".pptx", ".xlsx", ".zip"}

FORBIDDEN_PATHS = (
    re.compile(r"(^|/)(?:\.env(?:\..*)?|secrets\.toml)$", re.IGNORECASE),
    re.compile(r"(^|/)(?:private_data|restricted_data|client_data|uploads|snapshots)(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)(?:official_snapshots|private_snapshots)(/|$)", re.IGNORECASE),
    re.compile(r"\.(?:db|sqlite|sqlite3|i5z|pem|key|p12|pfx)$", re.IGNORECASE),
    re.compile(r"(^|/)ChemReg_Intel\.txt$", re.IGNORECASE),
)

SECRET_PATTERNS = (
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(rb"AKIA[0-9A-Z]{16}")),
    (
        "assigned secret",
        re.compile(
            rb"(?i)(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)"
            rb"\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{16,}"
        ),
    ),
)


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def scan_bytes(label: str, payload: bytes, findings: list[str]) -> None:
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(payload):
            findings.append(f"{label}: possible {name}")


def main() -> int:
    findings: list[str] = []
    paths = tracked_paths()

    for relative in paths:
        normalized = relative.replace("\\", "/")
        for pattern in FORBIDDEN_PATHS:
            if pattern.search(normalized):
                findings.append(f"{normalized}: forbidden public path")

        path = ROOT / relative
        if not path.is_file():
            continue

        scan_bytes(normalized, path.read_bytes(), findings)
        if path.suffix.lower() in ARCHIVE_SUFFIXES and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir() or member.file_size > 20_000_000:
                        continue
                    scan_bytes(f"{normalized}!{member.filename}", archive.read(member), findings)

    if findings:
        print("Public-repository audit failed:")
        for finding in sorted(set(findings)):
            print(f"- {finding}")
        return 1

    print(f"Public-repository audit passed for {len(paths)} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
