import hashlib
import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from generator.knowledge import retrieve
from generator.storage import artifact_path, event


class Handoff(TypedDict):
    sender: str
    recipient: str
    artifacts: list[str]
    feedback_count: int


class AgentState(TypedDict, total=False):
    artifacts: dict[str, Any]
    messages: list[Handoff]
    status: Literal["running", "needs_clarification", "failed", "completed"]
    feedback: list[dict[str, Any]]
    build_passed: bool
    review_passed: bool
    verification_passed: bool
    repairable: bool
    backend_repairs: int
    application_repairs: int
    current_stage: str
    failure_reason: str


Stage = Callable[[AgentState], AgentState]
Observer = Callable[[str, dict[str, Any]], None]


class RoleGraph:
    stages = (
        "analyst",
        "architect",
        "backend_models",
        "backend_service",
        "backend_routes",
        "backend_build",
        "backend_review",
        "backend_repair",
        "frontend_logic",
        "frontend_view",
        "tester",
        "documenter",
        "verification",
        "application_repair",
    )

    def __init__(
        self,
        nodes: Mapping[str, Stage],
        max_repairs: int = 2,
        observer: Observer | None = None,
    ):
        if set(nodes) != set(self.stages):
            raise ValueError(f"Expected role callbacks: {', '.join(self.stages)}")
        if max_repairs < 0:
            raise ValueError("Repair budget must be nonnegative")
        self.nodes = dict(nodes)
        self.max_repairs = max_repairs
        self.observer = observer

    def _run(self, name: str) -> Stage:
        def invoke(state: AgentState) -> AgentState:
            previous = state.get("current_stage", "input")
            messages = list(state.get("messages", []))
            handoff = Handoff(
                sender=previous,
                recipient=name,
                artifacts=sorted(state.get("artifacts", {})),
                feedback_count=len(state.get("feedback", [])),
            )
            messages.append(handoff)
            prepared = AgentState(**state)
            prepared.update(current_stage=name, messages=messages)
            if name in {"backend_repair", "application_repair"}:
                counter = "backend_repairs" if name == "backend_repair" else "application_repairs"
                prepared[counter] = state.get(counter, 0) + 1
            if self.observer:
                self.observer("agent_handoff", dict(handoff))
            update = self.nodes[name](prepared)
            if "messages" in update:
                raise ValueError("Role messages are graph-owned provenance")
            for counter in ("backend_repairs", "application_repairs"):
                if counter in update:
                    raise ValueError("Repair counters are graph-owned")
            gate_field = {
                "backend_build": "build_passed",
                "backend_review": "review_passed",
                "verification": "verification_passed",
            }.get(name)
            if (
                gate_field
                and update.get("status") not in {"failed", "needs_clarification"}
                and not isinstance(update.get(gate_field), bool)
            ):
                raise ValueError(f"Role {name} must explicitly report {gate_field}")
            prepared.update(update)
            prepared["artifacts"] = {
                **state.get("artifacts", {}),
                **update.get("artifacts", {}),
            }
            return prepared

        return invoke

    def _gate(self, state: AgentState, passed: str, success: str, repair: str) -> str:
        if state.get("status") in {"failed", "needs_clarification"}:
            return "stop"
        if state.get(passed) is True:
            return success
        counter = "backend_repairs" if repair == "backend_repair" else "application_repairs"
        if state.get("repairable", True) and state.get(counter, 0) < self.max_repairs:
            return repair
        return "exhausted"

    @staticmethod
    def _continue(state: AgentState) -> str:
        return "stop" if state.get("status") in {"failed", "needs_clarification"} else "next"

    @staticmethod
    def _exhausted(state: AgentState) -> AgentState:
        return AgentState(
            status="failed",
            failure_reason=state.get("failure_reason")
            or f"{state.get('current_stage', 'quality gate')} failed; repair budget exhausted or failure is not repairable",
        )

    @staticmethod
    def _complete(state: AgentState) -> AgentState:
        return AgentState(status="completed")

    def build_graph(self):
        graph = StateGraph(AgentState)
        for name in self.stages:
            graph.add_node(name, self._run(name))
        graph.add_node("exhausted", self._exhausted)
        graph.add_node("complete", self._complete)
        graph.add_edge(START, "analyst")
        chains = (
            ("analyst", "architect"),
            ("architect", "backend_models"),
            ("backend_models", "backend_service"),
            ("backend_service", "backend_routes"),
            ("backend_routes", "backend_build"),
            ("backend_repair", "backend_build"),
            ("frontend_logic", "frontend_view"),
            ("frontend_view", "tester"),
            ("tester", "documenter"),
            ("documenter", "verification"),
            ("application_repair", "verification"),
        )
        for source, target in chains:
            graph.add_conditional_edges(source, self._continue, {"next": target, "stop": END})
        graph.add_conditional_edges(
            "backend_build",
            lambda state: self._gate(state, "build_passed", "review", "backend_repair"),
            {
                "review": "backend_review",
                "backend_repair": "backend_repair",
                "stop": END,
                "exhausted": "exhausted",
            },
        )
        graph.add_conditional_edges(
            "backend_review",
            lambda state: self._gate(state, "review_passed", "frontend", "backend_repair"),
            {
                "frontend": "frontend_logic",
                "backend_repair": "backend_repair",
                "stop": END,
                "exhausted": "exhausted",
            },
        )
        graph.add_conditional_edges(
            "verification",
            lambda state: self._gate(
                state, "verification_passed", "complete", "application_repair"
            ),
            {
                "complete": "complete",
                "application_repair": "application_repair",
                "stop": END,
                "exhausted": "exhausted",
            },
        )
        graph.add_edge("exhausted", END)
        graph.add_edge("complete", END)
        return graph.compile()

    def invoke(self, initial: AgentState) -> AgentState:
        state = AgentState(status="running", backend_repairs=0, application_repairs=0)
        state.update(initial)
        with tracing_context(enabled=False):
            return self.build_graph().invoke(state, {"recursion_limit": 30 + self.max_repairs * 8})


SKILLS = {
    "analyst": "требования системный анализ роли сценарии критерии приемки ограничения",
    "architect": "архитектура ADR границы сервисов API данные интеграции события",
    "backend_models": "модель данных сущности API контракт схема ограничения миграции",
    "backend_service": "сервис бизнес логика транзакции события идемпотентность безопасность",
    "backend_routes": "API HTTP авторизация коды ошибок контракт версионирование",
    "backend_build": "сборка зависимости версии Docker",
    "backend_review": "проверка требований безопасность сценарии ошибки транзакции",
    "backend_repair": "исправление дефектов сервис API данные требования",
    "frontend_logic": "интерфейс роли сценарии API ошибки мобильное приложение",
    "frontend_view": "интерфейс экраны мобильное приложение доступность",
    "tester": "критерии приемки тестирование сценарии ошибки безопасность",
    "documenter": "документация системный анализ сервис API ADR требования",
    "verification": "проверка приемка безопасность сборка тестирование",
    "application_repair": "исправление дефектов критерии приемки требования",
}


@dataclass(frozen=True)
class SkillContext:
    text: str
    audit: dict[str, Any]


class SkillLoader:
    def __init__(
        self,
        root: Path,
        knowledge: Path,
        run_dir: Path,
        allowed_files: Mapping[str, Collection[str]],
        max_context_chars: int = 48000,
        max_knowledge_chars: int = 10000,
        chunk_limit: int = 3,
    ):
        if min(max_context_chars, max_knowledge_chars, chunk_limit) < 1:
            raise ValueError("Skill context limits must be positive")
        self.root = root
        self.knowledge = knowledge
        self.run_dir = run_dir
        self.allowed_files = {role: set(paths) for role, paths in allowed_files.items()}
        self.max_context_chars = max_context_chars
        self.max_knowledge_chars = max_knowledge_chars
        self.chunk_limit = chunk_limit

    def load(self, role: str, task: str, requested_files: Collection[str] = ()) -> SkillContext:
        if role not in SKILLS:
            raise ValueError(f"Unknown role skill: {role}")
        paths = list(dict.fromkeys(requested_files))
        if not set(paths) <= self.allowed_files.get(role, set()):
            raise ValueError(f"Role {role} requested files outside its context allowlist")
        files = []
        for name in paths:
            path = artifact_path(self.root, name)
            body = path.read_text(encoding="utf-8")
            files.append({"path": name, "text": body})
        chunks = retrieve(self.knowledge, SKILLS[role] + " " + task, limit=self.chunk_limit)
        selected = []
        used = 0
        for chunk in chunks:
            size = len(chunk["text"])
            if used + size <= self.max_knowledge_chars:
                selected.append(chunk)
                used += size
        payload = {"skill": role, "task": task, "regulations": selected, "files": files}
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) > self.max_context_chars:
            raise ValueError(
                f"Role {role} context has {len(text)} characters; split the task before generation (limit {self.max_context_chars})"
            )
        audit = {
            "role": role,
            "context_chars": len(text),
            "task_chars": len(task),
            "knowledge_chars": used,
            "retrieved_chunks": len(chunks),
            "selected_chunks": len(selected),
            "sources": [
                {"source": chunk["source"], "sha256": chunk["sha256"]} for chunk in selected
            ],
            "files": [
                {
                    "path": item["path"],
                    "chars": len(item["text"]),
                    "sha256": hashlib.sha256(item["text"].encode()).hexdigest(),
                }
                for item in files
            ],
        }
        event(self.run_dir, "skill_loaded", **audit)
        return SkillContext(text=text, audit=audit)
