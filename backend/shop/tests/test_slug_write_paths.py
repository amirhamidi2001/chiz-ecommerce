"""
Task 14.4.1.3 - guard: no code path may bypass Model.save() slug generation.

``bulk_create()`` does NOT call a model's custom save(), so a bulk path (e.g. the
Epic 17 CSV import) creating Product/Category/Brand/blog rows would silently store
slug "" - the exact bug ADR 0002 fixes. Passing an explicit ``slug=`` (as the old
seed command did via get_or_create(defaults={"slug": ...})) has the same effect:
it skips the collision loop, the fallback and the length cap.

Audit result at the time of writing: NO such path exists (the only bulk_create
calls are for ProductVariant / price snapshots in old data migrations). This test
keeps it that way. If you genuinely need to bulk-create slugged rows, either
iterate and .save(), or pre-compute slugs with shop.text_utils.persian_slugify +
unique_slug INCLUDING collisions between rows of the same batch, and add a test
that proves the path; then narrow this guard for that one call site.
"""

import ast
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[2]
SLUGGED = r"\b(Product|Category|Brand|Post)\b"  # \b: ProductVariant is NOT slugged
CREATORS = {"create", "get_or_create", "update_or_create"}
SKIP_DIRS = {"tests", "migrations", "node_modules", ".venv", "venv", "locale", "media"}


def find_violations(source, label="<source>"):
    """Return human-readable violations found in ``source`` (a Python module)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        receiver = ast.unparse(node.func.value)
        on_slugged = re.search(SLUGGED, receiver) is not None
        if node.func.attr == "bulk_create" and on_slugged:
            found.append(
                f"{label}:{node.lineno} bulk_create() on {receiver} skips save() slug generation"
            )
        if node.func.attr in CREATORS and on_slugged:
            keys = {kw.arg for kw in node.keywords}
            for kw in node.keywords:
                if kw.arg == "defaults" and isinstance(kw.value, ast.Dict):
                    keys |= {
                        k.value for k in kw.value.keys if isinstance(k, ast.Constant)
                    }
            if "slug" in keys:
                found.append(
                    f"{label}:{node.lineno} {node.func.attr}() on {receiver} passes slug explicitly"
                )
    return found


def production_python_files():
    for path in BACKEND.rglob("*.py"):
        parts = set(path.relative_to(BACKEND).parts)
        if (
            parts & SKIP_DIRS
            or path.name.startswith("test_")
            or path.name == "conftest.py"
        ):
            continue
        yield path


class TestDetectorCanFail:
    """A guard that can never fail is worthless: prove the detector works."""

    def test_flags_bulk_create_on_a_slugged_model(self):
        assert find_violations("Product.objects.bulk_create(rows)")
        assert find_violations("shop.models.Category.objects.bulk_create(rows)")
        assert find_violations("Post.objects.bulk_create(rows)")

    def test_flags_an_explicit_slug(self):
        assert find_violations(
            "Brand.objects.get_or_create(name=n, defaults={'slug': s})"
        )
        assert find_violations("Category.objects.create(name=n, slug=s)")

    def test_allows_the_safe_and_unrelated_patterns(self):
        assert not find_violations("ProductVariant.objects.bulk_create(rows)")
        assert not find_violations("Product.objects.create(name=n, price=p)")
        assert not find_violations("Brand.objects.get_or_create(name=n)")
        assert not find_violations("Review.objects.bulk_create(rows)")


def test_no_production_code_bypasses_save_slug_generation():
    violations = []
    for path in production_python_files():
        violations += find_violations(
            path.read_text(encoding="utf8"), str(path.relative_to(BACKEND))
        )
    assert violations == [], "\n".join(violations)


@pytest.mark.parametrize(
    "command",
    ["shop/management/commands/seed_shop.py", "blog/management/commands/seed_blog.py"],
)
def test_seed_commands_never_compute_slugs_themselves(command):
    tree = ast.parse((BACKEND / command).read_text(encoding="utf8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    assert "slugify" not in names and "persian_slugify" not in names
    assert "slug" not in {
        kw.arg for n in ast.walk(tree) if isinstance(n, ast.Call) for kw in n.keywords
    }
