"""The invariants in AGENTS.md, checked."""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imports(p: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(p.read_text())):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def test_the_product_never_imports_the_world_or_the_evaluations():
    for p in (ROOT / "src" / "screening").rglob("*.py"):
        assert not imports(p) & {"world", "evals"}, p


def test_the_world_does_not_read_the_products_settings():
    for p in (ROOT / "world").rglob("*.py"):
        assert "screening" not in imports(p)
        for name in ("platform.toml", "gates.toml", "designs.toml"):
            assert name not in p.read_text()


def test_thresholds_live_in_config():
    for rel in ("models/gate.py", "models/relevance.py", "monitoring/drift.py", "capacity/autoscale.py",
                "lifecycle/retirement.py", "platform.py"):
        code = "\n".join(line.split("#")[0] for line in (ROOT / "src" / "screening" / rel).read_text().splitlines())
        found = [x for x in re.findall(r"(?<![\w.\[])0\.\d+", code) if x not in ("0.0", "0.5")]
        assert not found, (rel, found)


def test_reports_are_generated():
    readme = (ROOT / "README.md").read_text()
    assert "<!-- results:start -->" in readme and "<!-- results:end -->" in readme
    assert json.loads((ROOT / "reports" / "dev.json").read_text())["world"] == "dev"
