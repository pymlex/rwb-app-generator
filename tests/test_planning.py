import pytest

from generator.models import ImplementationPlan
from generator.pipeline import service_groups, validate_plan


def plan(packages):
    return ImplementationPlan.model_validate(
        {
            "packages": [
                {
                    "methods": methods,
                    "requirement_ids": ["FR-001"],
                    "endpoint_paths": ["/api/v1/items"],
                    "purpose": "Persist items",
                }
                for methods in packages
            ]
        }
    )


def test_nested_generic_contract_preserves_complete_signatures_and_startup():
    source = """public interface IDomainService {
        Task Initialise();
        Task<OperationResult<List<ItemDto>>> List(Actor actor);
        Task<OperationResult<ItemDto>> Create(Actor actor, CreateRequest request, string? idempotencyKey);
        Task Tick();
        Task<OperationResult<ItemDto>> Get(Actor actor, string id);
    }"""
    groups = service_groups(source)
    assert groups[0] == ["Task Initialise();"]
    assert len([method for group in groups for method in group]) == 5
    assert groups[1][0] == "Task<OperationResult<List<ItemDto>>> List(Actor actor);"
    assert "string? idempotencyKey" in groups[1][1]
    assert all(len(group) <= 3 for group in groups)


@pytest.mark.parametrize(
    "groups",
    [
        [["Initialise"], ["List"]],
        [["Initialise"], ["List", "List", "Create"]],
        [["Initialise"], ["List", "Create", "Invented"]],
        [["List"], ["Initialise", "Create"]],
        [["Initialise", "List"], ["Create"]],
    ],
)
def test_delegation_rejects_omissions_duplicate_invented_and_mixed_startup(groups):
    with pytest.raises(ValueError, match="assign every method once"):
        validate_plan(plan(groups), {"Initialise", "List", "Create"}, {"FR-001"}, {"/api/v1/items"})


def test_delegation_accepts_complete_grounded_work_packages():
    validate_plan(
        plan([["Initialise"], ["List", "Create"]]),
        {"Initialise", "List", "Create"},
        {"FR-001"},
        {"/api/v1/items"},
    )


@pytest.mark.parametrize(
    "requirements,endpoints", [({"FR-999"}, {"/api/v1/items"}), ({"FR-001"}, {"/api/v1/other"})]
)
def test_delegation_rejects_ungrounded_requirements_or_endpoints(requirements, endpoints):
    with pytest.raises(ValueError, match="unknown requirements or API paths"):
        validate_plan(
            plan([["Initialise"], ["List", "Create"]]),
            {"Initialise", "List", "Create"},
            requirements,
            endpoints,
        )
