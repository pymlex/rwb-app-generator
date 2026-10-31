"""Publish a generated application using an ephemeral environment-only askpass."""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


ASKPASS = """#!/bin/sh
case "$1" in
  *Username*) printf '%s\\n' 'oauth2' ;;
  *Password*) printf '%s\\n' "$GITLAB_TOKEN" ;;
  *) exit 1 ;;
esac
"""
EXCLUDED_DIRS = {
    ".git",
    ".pipeline",
    ".ssh",
    ".aws",
    ".codex",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".angular",
    "bin",
    "obj",
    "dist",
}


def validate_remote(remote: str) -> str:
    if not remote or any(char.isspace() or ord(char) < 32 for char in remote):
        raise ValueError(
            "Remote must be a credential-free HTTPS URL or an absolute local bare path"
        )
    if Path(remote).is_absolute():
        path = Path(remote)
        if path.is_dir() and (path / "HEAD").is_file() and (path / "objects").is_dir():
            return str(path.resolve())
        raise ValueError("Local publication requires an existing bare repository")
    try:
        url = urlsplit(remote)
        valid = (
            url.scheme == "https"
            and url.hostname
            and url.username is None
            and url.password is None
            and not url.query
            and not url.fragment
            and url.path not in {"", "/"}
            and url.port != 0
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Remote must be an HTTPS repository URL without credentials, query or fragment"
        )
    return remote


def publish_files(root: Path) -> list[str]:
    files = []
    for directory, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in EXCLUDED_DIRS
            and not name.lower().startswith(".env")
            and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(names):
            path = Path(directory) / name
            if (
                name.lower().startswith(".env")
                or path.suffix.lower() in {".pem", ".key", ".pfx", ".p12", ".log"}
                or name in {"id_rsa", "id_ed25519"}
            ):
                continue
            if path.is_symlink():
                raise ValueError("Publication does not accept symlink artifacts")
            files.append(path.relative_to(root).as_posix())
    return sorted(files)


def publish(root: Path, remote: str) -> dict:
    remote = validate_remote(remote)
    if remote.startswith("https://") and "GITLAB_TOKEN" not in os.environ:
        raise ValueError("HTTPS publication requires GITLAB_TOKEN in the environment")
    root = root.resolve()
    identity_path = root / ".pipeline/input.sha256"
    if not identity_path.is_file() or identity_path.is_symlink():
        raise ValueError("Publication requires a generated run with .pipeline/input.sha256")
    fingerprint = identity_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("Invalid run fingerprint")
    git_dir = root / ".git"
    marker = git_dir / "rwb-generator-publish"
    if git_dir.exists() and (not git_dir.is_dir() or git_dir.is_symlink() or not marker.is_file()):
        raise ValueError(
            "Publication requires a fresh output directory or a repository created by publish"
        )
    files = publish_files(root)
    if not files:
        raise ValueError("No publishable application artifacts")
    with tempfile.TemporaryDirectory(prefix="rwb-publish-") as temporary:
        private = Path(temporary)
        askpass = private / "askpass"
        askpass.write_text(ASKPASS, encoding="utf-8")
        askpass.chmod(0o700)
        hooks = private / "hooks"
        hooks.mkdir()
        # Inherit the token without accessing its value in Python. Only askpass reads it.
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("GIT_")
        }
        environment.update(
            {
                "GIT_ASKPASS": str(askpass),
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_INDEX_FILE": str(private / "index"),
            }
        )
        command = [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            f"core.hooksPath={hooks}",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.proxy=",
            "-c",
            "user.name=RWB Generator",
            "-c",
            "user.email=generator@rwb.invalid",
            "-c",
            "commit.gpgsign=false",
        ]

        def git(arguments: list[str], data: bytes | None = None, allowed=(0,)) -> bytes:
            try:
                result = subprocess.run(
                    command + arguments,
                    cwd=root,
                    env=environment,
                    input=data,
                    capture_output=True,
                    timeout=180,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise RuntimeError(
                    "Git publication could not complete; no credentials or git output are logged"
                ) from None
            if result.returncode not in allowed:
                raise RuntimeError(
                    "Git publication failed during " + arguments[0] + "; git output suppressed"
                )
            return result.stdout

        if not git_dir.exists():
            git(["init", "--initial-branch=main"])
            marker.write_text("rwb-app-generator\n", encoding="utf-8")
        git(["config", "--local", "remote.origin.url", remote])
        git(["config", "--local", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"])
        ignored = set(
            git(
                ["check-ignore", "--no-index", "--stdin", "-z"],
                b"\0".join(os.fsencode(name) for name in files) + b"\0",
                allowed=(0, 1),
            ).split(b"\0")
        )
        files = [name for name in files if os.fsencode(name) not in ignored]
        if not files:
            raise ValueError("All application artifacts are ignored")
        git(["read-tree", "--empty"])
        git(
            ["add", "--force", "--pathspec-from-file=-", "--pathspec-file-nul"],
            b"\0".join(os.fsencode(":(literal)" + name) for name in files) + b"\0",
        )
        tree = git(["write-tree"]).strip()
        previous = git(["rev-parse", "--verify", "HEAD^{tree}"], allowed=(0, 128)).strip()
        if tree != previous:
            git(["commit", "-m", f"Generated application: run fingerprint {fingerprint}"])
        commit = git(["rev-parse", "--verify", "HEAD"]).decode().strip()
        shutil.copyfile(private / "index", git_dir / "index")
        # Explicit clean destination also avoids any inherited remote.origin.pushurl.
        git(["push", "--", remote, "HEAD:refs/heads/main"])
    return {
        "status": "published",
        "run_fingerprint": fingerprint,
        "commit": commit,
        "branch": "main",
    }
