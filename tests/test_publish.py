import json
import subprocess
import sys
from pathlib import Path

import pytest

from generator.publish import publish, validate_remote
from generator.storage import digest


@pytest.fixture
def publication(tmp_path):
    output = tmp_path / "app"
    (output / ".pipeline").mkdir(parents=True)
    fingerprint = digest("fixture requirements")
    (output / ".pipeline/input.sha256").write_text(fingerprint)
    (output / ".pipeline/responses").mkdir()
    (output / ".pipeline/responses/private.json").write_text('{"private":"exclude"}')
    (output / "README.md").write_text("# Generated app\n")
    (output / ".env").write_text("PRIVATE=exclude\n")
    (output / "signing.key").write_text("exclude\n")
    (output / ".gitignore").write_text("ignored.txt\n.env*\n.pipeline/\n")
    (output / "ignored.txt").write_text("exclude\n")
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(bare)],
        check=True,
        capture_output=True,
    )
    return output, bare, fingerprint


def bare_git(bare, *arguments):
    return subprocess.run(
        ["git", "--git-dir", str(bare), *arguments], check=True, capture_output=True, text=True
    ).stdout


def test_publish_cli_to_local_bare_without_credentials_in_repository(publication, monkeypatch):
    output, bare, fingerprint = publication
    token = "FAKE-GITLAB-TOKEN-FOR-TEST-ONLY"
    monkeypatch.setenv("GITLAB_TOKEN", token)
    result = subprocess.run(
        [sys.executable, "main.py", "publish", str(output), "--remote", str(bare)],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "published"
    assert payload["run_fingerprint"] == fingerprint
    assert bare_git(bare, "rev-parse", "main").strip() == payload["commit"]
    assert fingerprint in bare_git(bare, "log", "-1", "--format=%B")
    assert set(bare_git(bare, "ls-tree", "-r", "--name-only", "main").splitlines()) == {
        "README.md",
        ".gitignore",
    }
    config = (output / ".git/config").read_text()
    assert str(bare) in config
    assert token not in config + result.stdout + result.stderr
    assert "askpass" not in config.lower()
    assert not list(output.rglob("askpass"))
    assert publish(output, str(bare))["commit"] == payload["commit"]
    (output / "README.md").write_text("# Updated app\n")
    assert publish(output, str(bare))["commit"] != payload["commit"]
    assert bare_git(bare, "show", "main:README.md") == "# Updated app\n"


def test_askpass_uses_environment_and_is_removed(publication, monkeypatch):
    output, bare, _ = publication
    token = "FAKE-ASKPASS-TOKEN-ONLY"
    monkeypatch.setenv("GITLAB_TOKEN", token)
    # Git trace/config injection must not leak inherited configuration into the subprocess.
    monkeypatch.setenv("GIT_TRACE", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "credential.helper")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "unsafe-helper")
    original = subprocess.run
    helpers = []

    def observe(arguments, **kwargs):
        assert token not in " ".join(arguments)
        assert "GIT_TRACE" not in kwargs["env"]
        assert "GIT_CONFIG_COUNT" not in kwargs["env"]
        helper = Path(kwargs["env"]["GIT_ASKPASS"])
        assert helper.stat().st_mode & 0o777 == 0o700
        assert token not in helper.read_text()
        helpers.append(helper)
        if "push" in arguments:
            username = original(
                [str(helper), "Username for https://gitlab.example"],
                env=kwargs["env"],
                capture_output=True,
                text=True,
                check=True,
            )
            password = original(
                [str(helper), "Password for https://gitlab.example"],
                env=kwargs["env"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert username.stdout.strip() == "oauth2"
            assert password.stdout.strip() == token
        return original(arguments, **kwargs)

    monkeypatch.setattr(subprocess, "run", observe)
    publish(output, str(bare))
    assert helpers and all(not path.exists() for path in helpers)


@pytest.mark.parametrize(
    "remote",
    [
        "https://oauth2:FAKE-TOKEN@gitlab.example/team/app.git",
        "https://user@gitlab.example/team/app.git",
        "https://gitlab.example/app.git?token=FAKE",
        "https://gitlab.example/app.git#FAKE",
        "http://gitlab.example/app.git",
        "ssh://git@gitlab.example/app.git",
        "git@gitlab.example:app.git",
        "ext::unsafe-command",
        "--receive-pack=unsafe",
        "https://gitlab.example/app.git\n",
    ],
)
def test_credentials_and_unsafe_remotes_rejected_without_echoing_input(remote):
    with pytest.raises(ValueError) as error:
        validate_remote(remote)
    assert remote not in str(error.value)
    assert "FAKE" not in str(error.value)


def test_safe_https_url_is_accepted():
    assert (
        validate_remote("https://gitlab.example/team/app.git")
        == "https://gitlab.example/team/app.git"
    )


def test_failures_do_not_expose_git_output_and_clean_up(publication, monkeypatch):
    output, bare, _ = publication
    original = subprocess.run
    helpers = []

    def reject(arguments, **kwargs):
        helpers.append(Path(kwargs["env"]["GIT_ASKPASS"]))
        if "push" in arguments:
            return subprocess.CompletedProcess(arguments, 1, b"FAKE-SECRET", b"FAKE-SECRET")
        return original(arguments, **kwargs)

    monkeypatch.setattr(subprocess, "run", reject)
    with pytest.raises(RuntimeError) as error:
        publish(output, str(bare))
    assert "FAKE-SECRET" not in str(error.value)
    assert all(not helper.exists() for helper in helpers)


def test_existing_unrelated_repository_is_not_published(publication):
    output, bare, _ = publication
    (output / ".git").mkdir()
    with pytest.raises(ValueError, match="fresh output"):
        publish(output, str(bare))


def test_symlink_artifacts_are_rejected(publication):
    output, bare, _ = publication
    (output / "linked.txt").symlink_to(output / ".env")
    with pytest.raises(ValueError, match="symlink"):
        publish(output, str(bare))
