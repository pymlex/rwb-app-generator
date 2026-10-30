import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from generator.agents import AgentState, RoleGraph, SkillLoader
from generator.config import Settings
from generator.llm import OutputLimitExceeded, Qwen
from generator.models import (
    Analysis,
    ArtifactBatch,
    BackendReview,
    Blueprint,
    ImplementationPlan,
    RequirementReviews,
)
from generator.reference_data import profile_data, validate_contract
from generator.storage import digest, event, save_batch, source_span, write_json
from generator.verification import backend_build, report, verify
from generator.worker import RoleAgent


ROOT = Path(__file__).parent
BACKEND_FIXED = [
    "backend/Program.cs",
    "backend/DomainSupport.cs",
    "backend/DomainService.cs",
    "backend/App.csproj",
]
BACKEND_CONTRACT = ["backend/DomainModels.cs", "backend/migrations/002_domain.sql"]
FRONTEND = [
    "frontend/src/app.ts",
    "frontend/src/app.types.ts",
    "frontend/src/app.html",
    "frontend/src/app.css",
]


def service_groups(source: str) -> list[list[str]]:
    interface = re.search(r"interface\s+IDomainService\s*\{(.*?)\}", source, re.S)
    if interface is None:
        raise ValueError("Generated models must declare IDomainService")
    signatures = re.findall(r"Task(?:<[^;]+?>)?\s+\w+\s*\([^;]*?\)\s*;", interface.group(1), re.S)
    signatures = [re.sub(r"\s+", " ", value).strip() for value in signatures]
    initial = [value for value in signatures if re.search(r"\bInitialise\s*\(", value)]
    operations = [value for value in signatures if value not in initial]
    if len(initial) != 1 or not operations:
        raise ValueError("Domain service must expose Initialise and typed operations")
    return [initial, *[operations[index : index + 3] for index in range(0, len(operations), 3)]]


def validate_plan(
    plan: ImplementationPlan, methods: set[str], requirements: set[str], endpoints: set[str]
):
    assigned = [method for package in plan.packages for method in package.methods]
    if sorted(assigned) != sorted(methods) or plan.packages[0].methods != ["Initialise"]:
        raise ValueError("Implementation plan must assign every method once and Initialise first")
    for package in plan.packages:
        if (
            not set(package.requirement_ids) <= requirements
            or not set(package.endpoint_paths) <= endpoints
        ):
            raise ValueError("Work plan references unknown requirements or API paths")


class Pipeline:
    def __init__(self, settings: Settings, output: Path, knowledge: Path):
        self.settings = settings
        self.output = output.resolve()
        self.knowledge = knowledge
        self.run_dir = self.output / ".pipeline"
        self.model = Qwen(settings, self.run_dir)
        self.generated: dict[str, dict] = {}
        self.checks = []
        self.service_paths: list[str] = []
        self.test_paths: list[str] = []

    def prompt(self, name: str) -> str:
        return (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")

    def files(self, paths: list[str]) -> str:
        return "\n\n".join(
            f"FILE {path}\n{(self.output / path).read_text(encoding='utf-8')}" for path in paths
        )

    def context(self, role: str, task: dict, paths: list[str], requirements=None) -> str:
        loader = SkillLoader(
            self.output,
            self.knowledge,
            self.run_dir,
            {role: paths},
            max_context_chars=65000,
            max_knowledge_chars=8000,
            chunk_limit=2,
        )
        loaded = loader.load(role, json.dumps(task, ensure_ascii=False), paths)
        domain = {}
        if hasattr(self, "analysis"):
            domain = self.analysis.model_dump(exclude={"questions"})
            domain["requirements"] = [
                item.model_dump(exclude={"source_quote"})
                for item in (requirements or self.analysis.requirements)
            ]
        return (
            json.dumps(
                {"analysis": domain, "reference_data": self.reference_data}, ensure_ascii=False
            )
            + "\n"
            + loaded.text
        )

    def generate_files(self, stage: str, prompt: str, context: str, paths: list[str]):
        try:
            batch = self.ask(stage, prompt, context, ArtifactBatch)
        except OutputLimitExceeded:
            if len(paths) == 1:
                raise
            event(
                self.run_dir,
                "artifact_partitioned",
                stage=stage,
                paths=paths,
                reason="output_limit",
            )
            files = []
            for index, path in enumerate(paths):
                instruction = (
                    prompt
                    + "\nOUTPUT PARTITION OVERRIDE: generate exactly one file in result.files: "
                    + path
                    + ". Other requested artifacts are generated separately."
                )
                part = self.generate_files(f"{stage}-file-{index}", instruction, context, [path])
                files.extend(part.files)
                context += "\nALREADY GENERATED CONTRACT\n" + self.files([path])
            return ArtifactBatch(files=files)
        known = {item.id for item in self.analysis.requirements}
        for item in batch.files:
            if not set(item.requirement_ids) <= known:
                raise ValueError(f"Artifact {item.path} references unknown requirement identifiers")
        save_batch(self.output, batch, set(paths))
        for item in batch.files:
            self.generated[item.path] = item.model_dump(exclude={"content"})
        self.save_manifest()
        return batch

    def ask(self, stage: str, instruction: str, context: str, schema):
        platform = [
            str(path.relative_to(self.output).as_posix())
            for path in (self.output / "backend").glob("*")
            if path.is_file()
            and path.name
            in {
                "Program.cs",
                "DomainSupport.cs",
                "Store.cs",
                "OutboxPublisher.cs",
                "DomainService.cs",
                "App.csproj",
            }
        ]
        platform += ["backend/migrations/001_initial.sql"]
        if stage.startswith("analysis") or stage.startswith("architecture"):
            paths = ["docs/analysis.json", "docs/clarification-answers.json"]
        elif stage.startswith("backend-models") or stage.startswith("backend-plan"):
            paths = platform
        elif stage.startswith("backend-service"):
            paths = [*platform, *BACKEND_CONTRACT, *self.service_paths]
        else:
            paths = [
                *platform,
                *BACKEND_CONTRACT,
                *self.service_paths,
                "backend/Domain.cs",
                *FRONTEND,
                *self.test_paths,
            ]
        paths = [path for path in dict.fromkeys(paths) if (self.output / path).is_file()]
        agent = RoleAgent(self.model, self.output, self.knowledge, self.run_dir, paths)
        return agent.generate(stage, instruction, context, schema)

    def save_manifest(self):
        write_json(self.run_dir / "artifact-manifest.json", list(self.generated.values()))

    def analyst(self, state: AgentState) -> AgentState:
        context = self.context(
            "analyst", {"business_requirements": self.requirements, "answers": ""}, []
        )
        existing = self.output / "docs/analysis.json"
        if existing.exists():
            self.analysis = Analysis.model_validate_json(existing.read_text(encoding="utf-8"))
            event(self.run_dir, "analysis_reused", path="docs/analysis.json")
        else:
            self.analysis = self.ask("analysis", self.prompt("analysis"), context, Analysis)
        for requirement in self.analysis.requirements:
            requirement.source_quote = source_span(self.requirements, requirement.source_quote)
        identifiers = [item.id for item in self.analysis.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Requirement identifiers must be unique")
        supplied = json.loads(self.answers) if self.answers else {}
        questions = {
            f"Q-{index:03}": question for index, question in enumerate(self.analysis.questions, 1)
        }
        if not isinstance(supplied, dict) or not set(supplied) <= questions.keys():
            raise ValueError("Answers must map known Q identifiers to answers")
        for identifier, answer in supplied.items():
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Every supplied answer must be a nonempty string")
            questions[identifier].blocking = False
            resolved = f"Resolved clarification {identifier}: {answer}"
            if resolved not in self.analysis.assumptions:
                self.analysis.assumptions.append(resolved)
        write_json(self.output / "docs/analysis.json", self.analysis.model_dump())
        write_json(self.output / "docs/clarification-answers.json", supplied)
        blocking = [
            {"id": identifier, **question.model_dump()}
            for identifier, question in questions.items()
            if question.blocking
        ]
        write_json(self.output / "docs/clarifications.json", blocking)
        return AgentState(
            status="needs_clarification" if blocking else "running",
            artifacts={"analysis": "docs/analysis.json"},
        )

    def architect(self, state: AgentState) -> AgentState:
        context = self.context(
            "architect", {"task": "Design all workflows and exact typed API contracts"}, []
        )
        self.blueprint = self.ask("architecture", self.prompt("architecture"), context, Blueprint)
        known = {item.id for item in self.analysis.requirements}
        for endpoint in self.blueprint.endpoints:
            if not set(endpoint.requirement_ids) <= known:
                raise ValueError("API contract references unknown requirement identifiers")
        write_json(self.output / "docs/blueprint.json", self.blueprint.model_dump())
        return AgentState(artifacts={"blueprint": "docs/blueprint.json"})

    def backend_models(self, state: AgentState) -> AgentState:
        paths = BACKEND_CONTRACT
        defects = []
        for attempt in range(self.settings.max_repairs + 1):
            dependencies = ["backend/DomainSupport.cs", "backend/migrations/001_initial.sql"]
            if attempt:
                dependencies += paths
                event(self.run_dir, "repair_started", stage="contract", attempt=attempt)
            context = self.context(
                "backend_models",
                {"blueprint": self.blueprint.model_dump(), "contract_defects": defects},
                dependencies,
            )
            self.generate_files(
                f"backend-models-{attempt}", self.prompt("backend-models"), context, paths
            )
            defects = validate_contract(
                self.reference_data,
                (self.output / paths[0]).read_text(encoding="utf-8"),
                (self.output / paths[1]).read_text(encoding="utf-8"),
            )
            write_json(
                self.output / "reports/contract-check.json",
                {"passed": not defects, "defects": defects},
            )
            if not defects:
                return AgentState(artifacts={"backend_contract": paths})
        return AgentState(
            status="failed",
            failure_reason="Generated contract violates source data or fixed platform conventions",
            feedback=[{"defect": item} for item in defects],
        )

    def backend_service(self, state: AgentState) -> AgentState:
        source = (self.output / "backend/DomainModels.cs").read_text(encoding="utf-8")
        signatures = [method for group in service_groups(source) for method in group]
        by_name = {re.search(r"(\w+)\s*\(", method).group(1): method for method in signatures}
        if len(by_name) != len(signatures):
            raise ValueError(
                "Service operation names must be unique for deterministic work delegation"
            )
        planning = self.context(
            "architect",
            {"blueprint": self.blueprint.model_dump(), "available_methods": list(by_name)},
            BACKEND_CONTRACT,
        )
        plan = self.ask(
            "backend-plan", self.prompt("implementation-plan"), planning, ImplementationPlan
        )
        validate_plan(
            plan,
            set(by_name),
            {item.id for item in self.analysis.requirements},
            {item.path for item in self.blueprint.endpoints},
        )
        write_json(self.run_dir / "implementation-plan.json", plan.model_dump())
        self.service_paths = []
        self.work_packages = {}

        def implement(identifier: str, methods: list[str], package):
            path = f"backend/DomainService.Part{identifier}.cs"
            event(
                self.run_dir,
                "work_delegated",
                sender="engineering_lead",
                recipient=f"backend-service-{identifier}",
                methods=methods,
                requirement_ids=package.requirement_ids,
                output_path=path,
            )
            task = {
                "module": f"Part{identifier}",
                "output_path": path,
                "assigned_methods": methods,
                "blueprint": {
                    **self.blueprint.model_dump(),
                    "endpoints": [
                        item.model_dump()
                        for item in self.blueprint.endpoints
                        if item.path in package.endpoint_paths
                    ],
                },
                "purpose": package.purpose,
            }
            context = self.context(
                "backend_service",
                task,
                [*BACKEND_CONTRACT, "backend/DomainSupport.cs", "backend/DomainService.cs"],
                [item for item in self.analysis.requirements if item.id in package.requirement_ids],
            )
            instruction = self.prompt("backend-service")
            if identifier == "00":
                instruction += "\nThis is the startup module. Initialise loads real supplied data and deterministic demo fixtures. Define no background worker here. Other modules own time transitions."
            try:
                self.generate_files(f"backend-service-{identifier}", instruction, context, [path])
            except OutputLimitExceeded:
                if len(methods) == 1:
                    raise
                event(
                    self.run_dir,
                    "operation_group_partitioned",
                    module=identifier,
                    methods=methods,
                    reason="output_limit",
                )
                (self.output / path).unlink(missing_ok=True)
                self.generated.pop(path, None)
                split = len(methods) // 2
                implement(identifier + "A", methods[:split], package)
                implement(identifier + "B", methods[split:], package)
                return
            self.service_paths.append(path)
            self.work_packages[path] = package.model_dump()
            event(
                self.run_dir,
                "work_completed",
                sender=f"backend-service-{identifier}",
                recipient="engineering_lead",
                artifact=path,
                sha256=digest((self.output / path).read_text(encoding="utf-8")),
            )

        for index, package in enumerate(plan.packages):
            implement(f"{index:02}", [by_name[name] for name in package.methods], package)
        for obsolete in (self.output / "backend").glob("DomainService.Part*.cs"):
            relative = obsolete.relative_to(self.output).as_posix()
            if relative not in self.service_paths:
                obsolete.unlink()
                self.generated.pop(relative, None)
        self.save_manifest()
        write_json(self.run_dir / "service-modules.json", self.service_paths)
        write_json(self.run_dir / "work-packages.json", self.work_packages)
        return AgentState(artifacts={"backend_services": self.service_paths})

    def backend_routes(self, state: AgentState) -> AgentState:
        context = self.context(
            "backend_routes",
            {"blueprint": self.blueprint.model_dump()},
            [*BACKEND_CONTRACT, "backend/DomainSupport.cs", "backend/Program.cs"],
        )
        instruction = (
            self.prompt("backend-routes")
            + "\nDo not register DomainWorker. Time transitions must be evaluated in the declared service polling operations."
        )
        self.generate_files("backend-routes", instruction, context, ["backend/Domain.cs"])
        return AgentState(artifacts={"backend_routes": "backend/Domain.cs"})

    def backend_build(self, state: AgentState) -> AgentState:
        check = backend_build(self.output, self.execute, self.sudo_password)
        write_json(self.run_dir / "backend-build.json", check.model_dump())
        passed = check.status == "passed" or not self.execute
        repairable = check.status == "failed" and bool(re.search(r"error CS\d+", check.log))
        return AgentState(
            build_passed=passed,
            repairable=repairable,
            feedback=[] if passed else [check.model_dump()],
        )

    def backend_review(self, state: AgentState) -> AgentState:
        issues = []
        groups = [
            [*BACKEND_CONTRACT, "backend/Domain.cs"],
            *[[path, *BACKEND_CONTRACT] for path in self.service_paths],
        ]
        for index, paths in enumerate(groups):
            package = self.work_packages.get(paths[0])
            requirements = (
                [
                    item
                    for item in self.analysis.requirements
                    if package and item.id in package["requirement_ids"]
                ]
                if package
                else self.analysis.requirements
            )
            blueprint = self.blueprint.model_dump()
            if package:
                blueprint["endpoints"] = [
                    item.model_dump()
                    for item in self.blueprint.endpoints
                    if item.path in package["endpoint_paths"]
                ]
            context = self.context(
                "backend_review",
                {
                    "task": "Review supplied module only. Other interface methods are implemented in separate partial files. Fixed helpers are trusted platform primitives.",
                    "blueprint": blueprint,
                },
                paths,
                requirements,
            )
            reviewed = self.ask(
                f"backend-review-{index:02}", self.prompt("backend-review"), context, BackendReview
            )
            serious_found = any(issue.severity in {"critical", "high"} for issue in reviewed.issues)
            if reviewed.passes_static_review == serious_found:
                raise ValueError("Reviewer verdict contradicts its defect severities")
            for issue in reviewed.issues:
                if not set(issue.requirement_ids) <= {
                    item.id for item in self.analysis.requirements
                }:
                    raise ValueError("Reviewer cited an unknown requirement")
                if issue.path not in paths:
                    raise ValueError("Reviewer cited a file outside its supplied context")
                issue.source_quote = source_span(
                    (self.output / issue.path).read_text(encoding="utf-8"), issue.source_quote
                )
                issues.append(issue.model_dump())
        write_json(self.output / "reports/backend-review.json", issues)
        serious = [issue for issue in issues if issue["severity"] in {"critical", "high"}]
        return AgentState(review_passed=not serious, repairable=True, feedback=serious)

    def repair(self, state: AgentState, backend: bool) -> AgentState:
        attempt = state["backend_repairs" if backend else "application_repairs"]
        stage = "backend_repair" if backend else "application_repair"
        event(self.run_dir, "repair_started", stage=stage, attempt=attempt)
        allowed = (
            [*BACKEND_CONTRACT, *self.service_paths, "backend/Domain.cs"]
            if backend
            else [
                *BACKEND_CONTRACT,
                *self.service_paths,
                "backend/Domain.cs",
                *FRONTEND,
                *self.test_paths,
            ]
        )
        feedback = state.get("feedback", [])
        selected = set()
        for issue in feedback:
            if issue.get("path") in allowed:
                selected.add(issue["path"])
            log = issue.get("log", "")
            selected.update(path for path in allowed if Path(path).name in log)
        if not selected:
            selected = set(self.service_paths if backend else FRONTEND)
        for path in sorted(selected):
            related = [
                item
                for item in feedback
                if item.get("path") == path or Path(path).name in item.get("log", "")
            ]
            if not related:
                related = feedback
            dependencies = list(dict.fromkeys([path, *BACKEND_CONTRACT]))
            if path.startswith("frontend/"):
                dependencies = list(
                    dict.fromkeys(
                        [
                            path,
                            *[item for item in FRONTEND if (self.output / item).exists()],
                            "backend/DomainModels.cs",
                            "backend/Domain.cs",
                        ]
                    )
                )
            task = {
                "output_path": path,
                "defects": related,
                "task": "Correct the demonstrated defect. Preserve all requirements and interfaces. Do not weaken assertions or remove workflows. Return exactly the named file.",
            }
            context = self.context(stage, task, dependencies)
            self.generate_files(
                f"{stage.replace('_', '-')}-{attempt}-{Path(path).stem}",
                self.prompt("repair")
                + "\nGenerate exactly the output_path named in the task. Only this file may change.",
                context,
                [path],
            )
        return AgentState()

    def backend_repair(self, state: AgentState) -> AgentState:
        return self.repair(state, True)

    def frontend_logic(self, state: AgentState) -> AgentState:
        paths = FRONTEND[:2]
        context = self.context(
            "frontend_logic",
            {"blueprint": self.blueprint.model_dump()},
            [
                "backend/DomainModels.cs",
                "backend/Domain.cs",
                "frontend/src/main.ts",
                "frontend/package.json",
            ],
        )
        self.generate_files("frontend-logic", self.prompt("frontend-logic"), context, paths)
        return AgentState(artifacts={"frontend_logic": paths})

    def frontend_view(self, state: AgentState) -> AgentState:
        context = self.context(
            "frontend_view",
            {"task": "Create responsive Material UI for all supplied controller operations"},
            FRONTEND[:2],
        )
        self.generate_files("frontend-view", self.prompt("frontend-view"), context, FRONTEND[2:])
        return AgentState(artifacts={"frontend_view": FRONTEND[2:]})

    def tester(self, state: AgentState) -> AgentState:
        self.test_paths = []
        requirements = self.analysis.requirements
        for index in range(0, len(requirements), 4):
            subset = requirements[index : index + 4]
            path = f"tests/test_acceptance_{index // 4:02}.py"
            self.test_paths.append(path)
            context = self.context(
                "tester",
                {
                    "task": "Test every supplied requirement and its acceptance criteria independently",
                    "blueprint": self.blueprint.model_dump(),
                    "output_path": path,
                },
                ["backend/DomainModels.cs", "backend/Domain.cs", self.service_paths[0]],
                subset,
            )
            instruction = (
                self.prompt("tests")
                .replace("tests/test_acceptance.py", path)
                .replace(
                    "Implement at least 10 independent tests.",
                    "Implement independent tests for all assigned acceptance criteria, at least one successful workflow and one boundary or rejected operation per requirement. Use setUp to isolate state via the actual API. Do not assume mutations from another test.",
                )
            )
            self.generate_files(f"tests-{index // 4:02}", instruction, context, [path])
        self.review_assertions()
        return AgentState(artifacts={"tests": self.test_paths})

    def review_assertions(self):
        reviews = []
        for index, path in enumerate(self.test_paths):
            subset = self.analysis.requirements[index * 4 : index * 4 + 4]
            context = self.context(
                "tester",
                {"task": "Independent assertion review of the supplied requirement group"},
                [path, "backend/DomainModels.cs", "backend/Domain.cs"],
                subset,
            )
            result = self.ask(
                f"assertion-review-{index:02}",
                self.prompt("assertion-review"),
                context,
                RequirementReviews,
            )
            if {item.requirement_id for item in result.requirements} != {
                item.id for item in subset
            }:
                raise ValueError("Assertion reviewer must return exactly the assigned requirements")
            source = (self.output / path).read_text(encoding="utf-8")
            for reviewed in result.requirements:
                if reviewed.status == "passed" and (
                    reviewed.missing_criteria or not reviewed.evidence
                ):
                    raise ValueError("Passed assertion review needs complete concrete evidence")
                for proof in reviewed.evidence:
                    if proof.path != path or not proof.test_name.startswith(
                        "test_" + reviewed.requirement_id.replace("-", "_") + "_"
                    ):
                        raise ValueError(
                            "Assertion evidence must identify an assigned test and requirement"
                        )
                    proof.source_quote = source_span(source, proof.source_quote)
                    if not re.search(r"def\s+" + re.escape(proof.test_name) + r"\s*\(", source):
                        raise ValueError("Assertion reviewer cited a nonexistent test")
                reviews.append(reviewed.model_dump())
        write_json(self.output / "reports/requirement-review.json", reviews)

    def documenter(self, state: AgentState) -> AgentState:
        paths = [
            "docs/system-analysis.md",
            "docs/architecture.md",
            "docs/api.md",
            "docs/user-guide.md",
            "docs/development.md",
            "docs/limitations.md",
            "README.md",
        ]
        for index, path in enumerate(paths):
            context = self.context(
                "documenter",
                {
                    "task": f"Document {path} using the relevant corporate template. Mark unverified implementation claims explicitly.",
                    "blueprint": self.blueprint.model_dump(),
                },
                ["backend/DomainModels.cs", "backend/Domain.cs", "frontend/src/app.ts"],
            )
            self.generate_files(
                f"documentation-{index:02}",
                self.prompt("documentation") + "\nGenerate exactly this file: " + path,
                context,
                [path],
            )
        return AgentState(artifacts={"documentation": paths})

    def verification(self, state: AgentState) -> AgentState:
        self.checks = verify(self.output, self.execute, self.deploy, self.sudo_password)
        failed = [item for item in self.checks if item.status == "failed"]
        code_failures = [
            item for item in failed if item.name in {"build", "acceptance", "structure"}
        ]
        infra = [item for item in failed if item not in code_failures]
        repairable = bool(code_failures) and not infra
        if any(
            item.name == "build"
            and not re.search(r"error (CS|TS|NG)\d+|\[ERROR\] (TS|NG)", item.log)
            for item in failed
        ):
            repairable = False
        return AgentState(
            verification_passed=not failed,
            repairable=repairable,
            feedback=[item.model_dump() for item in failed],
        )

    def application_repair(self, state: AgentState) -> AgentState:
        result = self.repair(state, False)
        self.review_assertions()
        return result

    def run(
        self,
        requirements: str,
        answers: str = "",
        execute: bool = False,
        deploy: bool = False,
        sudo_password: str | None = None,
    ):
        started = time.monotonic()
        self.requirements, self.answers = requirements, answers
        self.execute, self.deploy, self.sudo_password = execute, deploy, sudo_password
        self.run_dir.mkdir(parents=True, exist_ok=True)
        identity = digest(requirements)
        identity_file = self.run_dir / "input.sha256"
        if identity_file.exists() and identity_file.read_text() != identity:
            raise ValueError(
                "Output directory belongs to different requirements. Use a new output directory."
            )
        identity_file.write_text(identity)
        event(self.run_dir, "run_started", input_sha256=identity)
        shutil.copytree(ROOT / "templates", self.output, dirs_exist_ok=True)
        shutil.copyfile(ROOT.parent / "LICENSE", self.output / "LICENSE")
        (self.output / "requirements.md").write_text(requirements, encoding="utf-8")
        self.reference_data = profile_data(self.output / "backend/data")
        write_json(self.run_dir / "reference-data.json", self.reference_data)
        manifest = self.run_dir / "artifact-manifest.json"
        if manifest.exists():
            self.generated = {
                item["path"]: item for item in json.loads(manifest.read_text(encoding="utf-8"))
            }
        if execute and not (self.output / ".env").exists():
            subprocess.run([sys.executable, str(self.output / "scripts/configure.py")], check=True)
        nodes = {name: getattr(self, name) for name in RoleGraph.stages}
        graph = RoleGraph(
            nodes, self.settings.max_repairs, lambda kind, data: event(self.run_dir, kind, **data)
        )
        state = graph.invoke(AgentState())
        write_json(self.run_dir / "graph-state.json", state)
        if state["status"] == "needs_clarification":
            return {
                "status": "needs_clarification",
                "questions": json.loads(
                    (self.output / "docs/clarifications.json").read_text(encoding="utf-8")
                ),
            }
        if not self.checks:
            return {
                "status": "failed",
                "stage": state.get("current_stage"),
                "reason": state.get("failure_reason"),
                "feedback": state.get("feedback", []),
            }
        result = report(self.output, self.analysis, self.checks, time.monotonic() - started)
        event(self.run_dir, "run_completed", **result)
        return result
