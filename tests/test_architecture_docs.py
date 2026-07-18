"""docs/ARCHITECTURE.md's class diagram must reference symbols that
actually exist in the codebase (E12/STORY-1203).

Morpheus's Sprint 5 architecture review found 3 stale references (a
class's fields, a method's signature, a whole sequence diagram) that no
automated check would have caught, since Mermaid diagrams and prose aren't
executable. This is a narrow, real guard against that recurring: it
verifies class *existence*, not full method-signature fidelity -- deeper
parsing for that would cost much more than it's worth here.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ARCHITECTURE_DOC = Path(__file__).resolve().parent.parent / "docs" / "ARCHITECTURE.md"
SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "scalene"

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
_CLASS_LINE_RE = re.compile(r"^\s*class\s+(\w+)\s*\{", re.MULTILINE)
_MODULE_STEREOTYPE_RE = re.compile(r"<<module:\s*([\w.]+)>>")


def find_class_diagram_block(markdown_text: str) -> str | None:
    """The mermaid code block whose first line is 'classDiagram' -- the
    doc has other mermaid blocks (sequence diagrams) that must be ignored."""
    for block in _MERMAID_BLOCK_RE.findall(markdown_text):
        if block.strip().startswith("classDiagram"):
            return block
    return None


def _class_exists_in(name: str, src_dir: Path) -> bool:
    pattern = re.compile(rf"^class {re.escape(name)}\b", re.MULTILINE)
    return any(pattern.search(f.read_text()) for f in src_dir.glob("*.py"))


def _module_stereotype_for(block: str, name: str) -> str | None:
    """A class entry may carry <<module: file.py>> instead of being a real
    class (e.g. a set of module-level functions documented as a box for
    readability) -- satisfied if that file exists, not by a class lookup."""
    match = re.search(rf"class\s+{re.escape(name)}\s*\{{(.*?)\}}", block, re.DOTALL)
    if not match:
        return None
    stereotype = _MODULE_STEREOTYPE_RE.search(match.group(1))
    return stereotype.group(1) if stereotype else None


def find_stale_class_references(block: str, src_dir: Path) -> list[str]:
    """Every 'class Name {' entry in a classDiagram block that resolves to
    neither a real class in src_dir nor a valid <<module: ...>> stereotype."""
    stale = []
    for name in _CLASS_LINE_RE.findall(block):
        if _class_exists_in(name, src_dir):
            continue
        module_file = _module_stereotype_for(block, name)
        if module_file and (src_dir / module_file).exists():
            continue
        stale.append(name)
    return stale


class TestArchitectureClassDiagram(unittest.TestCase):
    def test_class_diagram_block_is_found(self):
        text = ARCHITECTURE_DOC.read_text()
        block = find_class_diagram_block(text)
        self.assertIsNotNone(block, "No 'classDiagram' mermaid block found in docs/ARCHITECTURE.md")
        self.assertIn("class ", block)

    def test_every_diagrammed_class_exists_in_source_or_is_a_documented_module(self):
        text = ARCHITECTURE_DOC.read_text()
        block = find_class_diagram_block(text)
        stale = find_stale_class_references(block, SRC_DIR)
        self.assertEqual(
            stale,
            [],
            f"docs/ARCHITECTURE.md's class diagram references {stale}, which no longer exist "
            f"as real classes in src/scalene/ and have no valid <<module: ...>> stereotype -- "
            f"the diagram has drifted from the code.",
        )


class TestDriftDetectionLogicIsNotANoOp(unittest.TestCase):
    """Proves the check actually flags a stale reference, against a
    synthetic snippet -- not the real doc, which should currently pass."""

    def test_a_renamed_class_is_flagged_as_stale(self):
        synthetic_block = """classDiagram
    class TaintState {
        +str session_id
    }
    class ThisClassWasRenamedAndNoLongerExists {
        +str foo
    }
"""
        stale = find_stale_class_references(synthetic_block, SRC_DIR)
        self.assertEqual(stale, ["ThisClassWasRenamedAndNoLongerExists"])

    def test_a_valid_module_stereotype_is_not_flagged(self):
        synthetic_block = """classDiagram
    class ResourceVerifier {
        <<module: resource_verifier.py>>
    }
"""
        stale = find_stale_class_references(synthetic_block, SRC_DIR)
        self.assertEqual(stale, [])

    def test_an_invalid_module_stereotype_is_flagged(self):
        synthetic_block = """classDiagram
    class SomeModule {
        <<module: this_file_does_not_exist.py>>
    }
"""
        stale = find_stale_class_references(synthetic_block, SRC_DIR)
        self.assertEqual(stale, ["SomeModule"])

    def test_a_real_class_is_not_flagged(self):
        synthetic_block = """classDiagram
    class TaintState {
        +str session_id
    }
"""
        stale = find_stale_class_references(synthetic_block, SRC_DIR)
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
