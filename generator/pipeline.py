import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from tqdm.auto import tqdm

from generator.config import Settings
from generator.knowledge import retrieve
from generator.llm import Qwen
from generator.models import Analysis, ArtifactBatch, Blueprint
from generator.storage import digest, event, save_batch, write_json
from generator.verification import report, verify


ROOT = Path(__file__).parent


class Pipeline:
    def __init__(self, settings: Settings, output: Path, knowledge: Path):
        self.settings = settings
        self.output = output.resolve()
        self.knowledge = knowledge
        self.run_dir = self.output / ".pipeline"
        self.model = Qwen(settings, self.run_dir)

    def prompt(self, name: str) -> str:
        return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")

    def context(self, paths: list[str]) -> str:
        return "\n\n".join(
            f"FILE {path}\n{(self.output / path).read_text(encoding='utf-8')}"
            for path in paths if (self.output / path).exists()
        )

    def run(self, requirements: str, answers: str = "", execute: bool = False, deploy: bool = False, sudo_password: str | None = None):
        started = time.monotonic()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        identity = digest(requirements)
        identity_file = self.run_dir / "input.sha256"
        if identity_file.exists() and identity_file.read_text() != identity:
            raise ValueError("Output directory belongs to different requirements. Use a new output directory.")
        identity_file.write_text(identity)
        event(self.run_dir, "run_started", input_sha256=identity)
        shutil.copytree(ROOT / "templates", self.output, dirs_exist_ok=True)
        shutil.copyfile(ROOT.parent / "LICENSE", self.output / "LICENSE")
        (self.output / "requirements.md").write_text(requirements, encoding="utf-8")
        knowledge = retrieve(self.knowledge, requirements + " требования API UML сценарии ошибки безопасность", limit=4)
        write_json(self.run_dir / "retrieval.json", knowledge)
        context = json.dumps({"business_requirements": requirements, "answers": answers, "regulations": knowledge}, ensure_ascii=False)
        progress = tqdm(total=7, desc="Generation", unit="stage")
        analysis = self.model.generate("analysis", self.prompt("analysis"), context, Analysis)
        for requirement in analysis.requirements:
            if requirement.source_quote not in requirements:
                raise ValueError(f"Requirement {requirement.id} has no exact source quote")
        identifiers = [requirement.id for requirement in analysis.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Requirement identifiers must be unique")
        write_json(self.output / "docs" / "analysis.json", analysis.model_dump())
        blocking = [question.model_dump() for question in analysis.questions if question.blocking]
        if blocking:
            write_json(self.output / "docs" / "clarifications.json", blocking)
            event(self.run_dir, "needs_clarification", questions=blocking)
            progress.close()
            return {"status": "needs_clarification", "questions": blocking}
        progress.update()
        context += "\nANALYSIS\n" + analysis.model_dump_json()
        blueprint = self.model.generate("architecture", self.prompt("architecture"), context, Blueprint)
        known = set(identifiers)
        for endpoint in blueprint.endpoints:
            if not set(endpoint.requirement_ids) <= known:
                raise ValueError("API contract references unknown requirement identifiers")
        write_json(self.output / "docs" / "blueprint.json", blueprint.model_dump())
        context += "\nBLUEPRINT\n" + blueprint.model_dump_json()
        progress.update()
        backend_paths = {"backend/Domain.cs", "backend/migrations/002_domain.sql"}
        backend_context = context + "\n" + self.context(["backend/Program.cs", "backend/Store.cs", "backend/App.csproj"])
        backend = self.model.generate("backend", self.prompt("backend"), backend_context, ArtifactBatch)
        save_batch(self.output, backend, backend_paths)
        progress.update()
        frontend_context = context + "\n" + self.context(["backend/Domain.cs", "frontend/src/main.ts", "frontend/package.json"])
        frontend = self.model.generate("frontend", self.prompt("frontend"), frontend_context, ArtifactBatch)
        save_batch(self.output, frontend, {"frontend/src/app.ts"})
        progress.update()
        tests_context = context + "\n" + self.context(["backend/Domain.cs", "frontend/src/app.ts"])
        tests = self.model.generate("tests", self.prompt("tests"), tests_context, ArtifactBatch)
        save_batch(self.output, tests, {"tests/test_acceptance.py"})
        progress.update()
        docs = self.model.generate("documentation", self.prompt("documentation"), tests_context, ArtifactBatch)
        save_batch(self.output, docs, {
            "docs/system-analysis.md", "docs/architecture.md", "docs/api.md",
            "docs/user-guide.md", "docs/development.md", "docs/limitations.md", "README.md",
        })
        progress.update()
        write_json(self.run_dir / "artifact-manifest.json", [
            item.model_dump(exclude={"content"}) for batch in [backend, frontend, tests, docs] for item in batch.files
        ])
        if execute and not (self.output / ".env").exists():
            subprocess.run([sys.executable, str(self.output / "scripts" / "configure.py")], check=True)
        checks = verify(self.output, execute, deploy, sudo_password)
        for attempt in range(self.settings.max_repairs):
            failed = [check for check in checks if check.status == "failed"]
            if not failed:
                break
            event(self.run_dir, "repair_started", attempt=attempt + 1)
            repair_context = tests_context + "\nCURRENT FILES\n" + self.context([
                "backend/Domain.cs", "backend/migrations/002_domain.sql", "frontend/src/app.ts", "tests/test_acceptance.py",
            ]) + "\nFAILED CHECKS\n" + json.dumps([check.model_dump() for check in failed])
            repair = self.model.generate(
                f"repair-{attempt + 1}", self.prompt("repair"), repair_context, ArtifactBatch,
            )
            allowed = backend_paths | {"frontend/src/app.ts", "tests/test_acceptance.py"}
            if not {item.path for item in repair.files} <= allowed:
                raise ValueError("Repair attempted to modify the fixed platform")
            save_batch(self.output, repair)
            checks = verify(self.output, execute, deploy, sudo_password)
        progress.update()
        progress.close()
        result = report(self.output, analysis, checks, time.monotonic() - started)
        event(self.run_dir, "run_completed", **result)
        return result
