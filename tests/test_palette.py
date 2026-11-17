"""Palette discipline from docs/ART_AND_AUDIO_DIRECTION.md section 6.

Colors may only be defined in src/overload/art/palette.py. The scanner parses each file,
so comments and docstrings never trigger it. It flags:
- hex color strings (#RGB, #RGBA, #RRGGBB, #RRGGBBAA), alone or inside a longer string
- pygame color names such as "red" used as a string literal
- 0xRRGGBB integer literals
- tuples or lists of three or four integers from 0 to 255
- any construction of pygame's Color class, however it was imported
"""

import ast
import re
from pathlib import Path

import pygame
import pytest

from overload.art import palette

SRC = Path(__file__).resolve().parents[1] / "src" / "overload"
PALETTE_FILE = SRC / "art" / "palette.py"
HEX_IN_STRING = re.compile(r"#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b")
HEX_INT = re.compile(r"0[xX][0-9A-Fa-f]{6}\b")
COLOR_NAMES = frozenset(pygame.color.THECOLORS)


def _is_byte(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int and 0 <= node.value <= 255


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _color_aliases(tree: ast.AST) -> set[str]:
    aliases = {"Color"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("pygame"):
            for name in node.names:
                if name.name == "Color":
                    aliases.add(name.asname or name.name)
    return aliases


COLOR_ARG = {"fill": 0, "set_at": 1, "render": 2}
COLOR_KEYWORDS = {"color", "colour", "background", "bgcolor", "setcolor", "unsetcolor"}


def _color_slots(tree: ast.AST) -> set[int]:
    """Nodes that sit where pygame expects a color. Tuples elsewhere (rects, positions, loop
    values) are coordinates and are not flagged."""
    slots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            index = COLOR_ARG.get(name)
            owner = func.value if isinstance(func, ast.Attribute) else None
            if (isinstance(owner, ast.Attribute) and owner.attr == "draw") or (
                isinstance(owner, ast.Name) and owner.id == "draw"
            ):
                index = 1
            if index is not None and len(node.args) > index:
                slots.add(id(node.args[index]))
            for keyword in node.keywords:
                if keyword.arg in COLOR_KEYWORDS:
                    slots.add(id(keyword.value))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and re.search("colou?r", target.id.lower()):
                    slots.add(id(node.value))
    return slots


def color_literals(source: str) -> list[int]:
    """Return the line numbers of color literals in Python source."""
    tree = ast.parse(source)
    skip = _docstring_ids(tree)
    slots = _color_slots(tree)
    aliases = _color_aliases(tree)
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            if HEX_IN_STRING.search(node.value) or node.value.lower() in COLOR_NAMES:
                lines.add(node.lineno)
        elif isinstance(node, ast.Tuple | ast.List) and id(node) in slots:
            if len(node.elts) in (3, 4) and all(_is_byte(e) for e in node.elts):
                lines.add(node.lineno)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in aliases:
                lines.add(node.lineno)
    for lineno, line in enumerate(source.splitlines(), 1):
        code = line.split("#", 1)[0]
        if HEX_INT.search(code):
            lines.add(lineno)
    return sorted(lines)


def test_tokens_are_valid_hex() -> None:
    for name, value in palette.TOKENS.items():
        assert re.fullmatch(r"#[0-9A-F]{6}", value), f"{name} has malformed value {value}"


def test_rgb_converts_tokens() -> None:
    assert palette.rgb("fx.flash") == (255, 255, 255)
    assert palette.rgb("bg.void") == (10, 14, 23)


def test_unknown_token_is_rejected() -> None:
    with pytest.raises(KeyError):
        palette.rgb("not.a.token")


@pytest.mark.parametrize(
    "snippet",
    [
        'screen.fill("#FF0000")',
        'screen.fill("#F00")',
        'label = "glow #12ab34ff"',
        'screen.fill("red")',
        "screen.fill((255, 0, 0))",
        "screen.fill([10, 20, 30, 40])",
        "screen.fill(0xFF00AA)",
        "import pygame\nc = pygame.Color(1, 2, 3)",
        "from pygame import Color as C\nc = C('x')",
        "pygame.draw.circle(s, (1, 2, 3), (5, 5), 2)",
        "from pygame import draw\ndraw.line(s, (9, 9, 9), (0, 0), (1, 1))",
        "s.set_at((1, 1), (9, 9, 9))",
        'font.render("x", False, (1, 2, 3))',
        "glow_color = (10, 20, 30)",
        "make(color=(1, 2, 3))",
    ],
)
def test_scanner_catches_color_literals(snippet: str) -> None:
    assert color_literals(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        '"""A docstring that mentions Color( and "red" and #FFFFFF."""',
        "# fill((255, 0, 0)) in a comment\nx = 1",
        "size = (1280, 720)",
        "point = (300, 400, 500)",
        'name = "Regulator"',
        "frames = [1, 2]",
        "width, height, gap = 16, 18, 4",
        "for x in (4, 14, 24):\n    pass",
        "pygame.draw.rect(s, rgb('ui.text'), (7, 7, 5, 7), 1)",
        "s.fill(rgb('ui.text'), (8, 6, 3, 1))",
        "s.set_at((1, 2), rgb('ui.text'))",
    ],
)
def test_scanner_ignores_non_colors(snippet: str) -> None:
    assert not color_literals(snippet), snippet


def test_no_color_literals_outside_palette() -> None:
    offenders = []
    for path in SRC.rglob("*.py"):
        if path == PALETTE_FILE:
            continue
        for lineno in color_literals(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(SRC)}:{lineno}")
    assert not offenders, "Use overload.art.palette instead of color literals: " + ", ".join(
        offenders
    )
