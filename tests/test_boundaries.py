"""Structural enforcement of the module boundary rules.

These tests parse the source tree rather than exercise behaviour, so a future
change that quietly couples two modules fails CI instead of passing review.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from storeops.core import errors as errors_module
from storeops.core.config import Settings
from storeops.main import create_app

SRC = Path(__file__).resolve().parents[1] / "src"
PACKAGE = SRC / "storeops"
MODULES_DIR = PACKAGE / "modules"

MODULE_NAMES = frozenset({"activities", "programmes", "staff", "alerts", "reports"})
STAFF_PUBLIC_PORT = "storeops.modules.staff.port"

EXPECTED_ENDPOINTS = 10


def _module_files() -> list[Path]:
    return sorted(path for path in MODULES_DIR.rglob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def _owning_module(path: Path) -> str:
    return path.relative_to(MODULES_DIR).parts[0]


def _internal_imports(path: Path) -> set[str]:
    return {name for name in _imports(path) if name.startswith("storeops")}


def _module_of_import(name: str) -> str | None:
    parts = name.split(".")
    if len(parts) >= 3 and parts[:2] == ["storeops", "modules"]:
        return parts[2]
    return None


# ------------------------------------------------------------ rule 1 --------


def test_modules_import_only_core_themselves_or_the_staff_port() -> None:
    violations: list[str] = []
    for path in _module_files():
        owner = _owning_module(path)
        for name in _internal_imports(path):
            allowed = (
                name == "storeops"
                or name.startswith("storeops.core")
                or name.startswith(f"storeops.modules.{owner}")
                or name == STAFF_PUBLIC_PORT
            )
            if not allowed:
                violations.append(f"{path.relative_to(SRC)} imports {name}")

    assert violations == []


def test_module_graph_is_acyclic() -> None:
    graph: dict[str, set[str]] = {name: set() for name in MODULE_NAMES}
    for path in _module_files():
        owner = _owning_module(path)
        for name in _internal_imports(path):
            target = _module_of_import(name)
            if target and target != owner:
                graph[owner].add(target)

    visiting: set[str] = set()
    done: set[str] = set()
    cycles: list[str] = []

    def walk(node: str, trail: tuple[str, ...]) -> None:
        if node in visiting:
            cycles.append(" -> ".join((*trail, node)))
            return
        if node in done:
            return
        visiting.add(node)
        for neighbour in sorted(graph[node]):
            walk(neighbour, (*trail, node))
        visiting.discard(node)
        done.add(node)

    for node in sorted(graph):
        walk(node, ())

    assert cycles == []


# ------------------------------------------------------------ rule 2 --------


def test_no_module_imports_the_alerts_package() -> None:
    """Notification is the bus's job. Importing alerts defeats the whole design."""
    offenders = [
        f"{path.relative_to(SRC)} imports {name}"
        for path in _module_files()
        if _owning_module(path) != "alerts"
        for name in _internal_imports(path)
        if _module_of_import(name) == "alerts"
    ]

    assert offenders == []


def test_alerts_reacts_only_to_core_event_types() -> None:
    subscribers = MODULES_DIR / "alerts" / "subscribers.py"
    cross_module = {
        name
        for name in _internal_imports(subscribers)
        if (target := _module_of_import(name)) and target != "alerts"
    }

    assert cross_module == set()


# ------------------------------------------------------------ rule 3 --------


def test_staff_is_read_only_to_other_modules() -> None:
    offenders = [
        f"{path.relative_to(SRC)} imports {name}"
        for path in _module_files()
        if _owning_module(path) != "staff"
        for name in _internal_imports(path)
        if _module_of_import(name) == "staff" and name != STAFF_PUBLIC_PORT
    ]

    assert offenders == []


def test_staff_port_declares_no_mutating_methods() -> None:
    source = (MODULES_DIR / "staff" / "port.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }

    forbidden = {"create", "update", "delete", "save", "add", "replace", "deactivate"}
    assert names & forbidden == set()


# ------------------------------------------------------------ rule 4 --------


def test_core_never_imports_a_feature_module() -> None:
    offenders = [
        f"{path.relative_to(SRC)} imports {name}"
        for path in (PACKAGE / "core").rglob("*.py")
        for name in _internal_imports(path)
        if name.startswith("storeops.modules")
    ]

    assert offenders == []


def test_only_main_composes_multiple_modules() -> None:
    for path in PACKAGE.glob("*.py"):
        if path.name == "main.py":
            continue
        touched = {
            target
            for name in _internal_imports(path)
            if (target := _module_of_import(name))
        }
        assert len(touched) <= 1, f"{path.name} composes {sorted(touched)}"


# ------------------------------------------- typed errors everywhere --------


@pytest.mark.parametrize("layer", ["service.py", "routes.py"])
def test_services_and_routes_raise_only_app_errors(layer: str) -> None:
    allowed = set(errors_module.__all__)
    offenders: list[str] = []

    for module_name in sorted(MODULE_NAMES):
        path = MODULES_DIR / module_name / layer
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue  # bare `raise` re-raises, which is fine
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(raised, ast.Attribute):
                raised = raised.value
            name = raised.id if isinstance(raised, ast.Name) else ast.dump(raised)
            if name not in allowed:
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno} raises {name}")

    assert offenders == []


def test_every_error_class_subclasses_app_error() -> None:
    for name in errors_module.__all__:
        error_type = getattr(errors_module, name)
        assert issubclass(error_type, errors_module.AppError)
        assert isinstance(error_type.code, str)
        assert 400 <= error_type.status_code <= 599


# ------------------------------------------------- the 9 REST endpoints -----


def test_api_exposes_exactly_the_expected_endpoints() -> None:
    """The REST surface is a reviewed contract, so it is asserted exactly.

    Enumerated from the generated OpenAPI schema rather than `app.routes`:
    FastAPI 0.141 / Starlette 1.7 register an included router as a single lazy
    wrapper instead of copying each `APIRoute` onto the app, so walking
    `app.routes` sees only the routes declared directly on `main`.
    """
    schema = create_app(Settings(api_prefix="/api/v1")).openapi()
    operations = sorted(
        (path, method.upper())
        for path, handlers in schema["paths"].items()
        if path.startswith("/api/v1")
        for method in handlers
    )

    assert len(operations) == EXPECTED_ENDPOINTS, operations
    assert operations == [
        ("/api/v1/activities", "GET"),
        ("/api/v1/activities", "POST"),
        ("/api/v1/activities/bulk-status", "PATCH"),
        ("/api/v1/activities/{activity_id}/complete", "POST"),
        ("/api/v1/alerts", "GET"),
        ("/api/v1/alerts/{alert_id}/acknowledge", "POST"),
        ("/api/v1/programmes", "GET"),
        ("/api/v1/programmes", "POST"),
        ("/api/v1/reports/metrics", "GET"),
        ("/api/v1/staff", "GET"),
    ]


def test_every_module_contributes_all_three_layers() -> None:
    for module_name in sorted(MODULE_NAMES):
        for layer in ("routes.py", "service.py", "repository.py"):
            assert (MODULES_DIR / module_name / layer).is_file(), f"{module_name}/{layer}"
