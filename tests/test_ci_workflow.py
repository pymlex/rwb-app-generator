import os
import shutil
import subprocess
from pathlib import Path

import yaml


def test_gitleaks_uses_and_cleans_a_private_temporary_directory(tmp_path):
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    )
    steps = workflow["jobs"]["gitleaks"]["steps"]
    prepare = next(step for step in steps if step.get("id") == "gitleaks_tmp")
    scan = next(step for step in steps if step.get("uses", "").startswith("gitleaks/"))
    cleanup = next(step for step in steps if step.get("name") == "Remove Gitleaks temporary directory")
    assert steps.index(prepare) < steps.index(scan) < steps.index(cleanup)
    assert scan["env"]["TMPDIR"] == "${{ steps.gitleaks_tmp.outputs.path }}"
    assert cleanup["if"] == "always()"
    assert cleanup["env"]["GITLEAKS_TMP"] == "${{ steps.gitleaks_tmp.outputs.path }}"

    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    stale = runner_temp / "gitleaks.tmp"
    stale.write_text("previous download")
    paths = []
    for index in range(2):
        output = tmp_path / f"output-{index}"
        output.touch()
        env = {**os.environ, "RUNNER_TEMP": str(runner_temp), "GITHUB_OUTPUT": str(output)}
        subprocess.run(["bash", "-e", "-c", prepare["run"]], env=env, check=True)
        key, value = output.read_text().strip().split("=", 1)
        assert key == "path"
        path = Path(value)
        assert path.parent == runner_temp
        assert path.is_dir()
        paths.append(path)
    assert paths[0] != paths[1]

    node = shutil.which("node")
    if node:
        result = subprocess.run(
            [node, "-p", "require('os').tmpdir()"],
            env={**os.environ, "TMPDIR": str(paths[0])},
            check=True,
            text=True,
            capture_output=True,
        )
        assert result.stdout.strip() == str(paths[0])

    for path in paths:
        (path / "gitleaks.tmp").touch()
        subprocess.run(
            ["bash", "-e", "-c", cleanup["run"]],
            env={**os.environ, "GITLEAKS_TMP": str(path)},
            check=True,
        )
        assert not path.exists()
    assert stale.read_text() == "previous download"
