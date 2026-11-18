"""Draws the menu (game/menu.py) at the view's 256 x 144: the hub, LOADOUT, FUSE with its
cards, spin and reveal, and CONTROLS. Rarity always shows by shape first (1, 2 or 3 cross
marks and the card frame), then color (art direction, rarity tokens)."""

from __future__ import annotations

import pygame

from overload.art.palette import rgb, rgba
from overload.art.pixel import effects, hud
from overload.game.menu import (
    LOADOUT_ROWS,
    Menu,
    loadout_rows,
    percentages,
    roll_terms,
)
from overload.game.title import CONTROLS
from overload.sim.powers import (
    BASE_POWERS,
    FUSED,
    INGREDIENTS,
    NAMES,
    RECIPE_ORDER,
    cooldown_of,
    owned_result,
    rarity_of,
)
from overload.sim.tuning import TICK_RATE

PANEL = pygame.Rect(8, 6, 240, 132)
CARD_W, CARD_H = 72, 54


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def _frame(screen: pygame.Surface) -> tuple[int, int, int]:
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill(rgba("px.outline", 215))
    screen.blit(shade, (0, 0))
    screen.fill(rgb("px.outline"), PANEL)
    pygame.draw.rect(screen, rgb("px.wall.2"), PANEL, 1)
    return PANEL.x + 6, PANEL.right - 6, PANEL.y + 4


def _header(screen, title: str, right_text: str, left: int, right: int, top: int) -> None:
    hud.text(screen, title, (left, top), "ui.text")
    if right_text:
        hud.text(screen, right_text, (right, top), "ui.dim", "topright")
    screen.fill(rgb("px.wall.1"), (left, top + 11, right - left, 1))


def _footer(screen, text: str, left: int) -> None:
    hud.text(screen, text, (left, PANEL.bottom - 11), "ui.dim")


def _icon(power: str, scale: int = 1, hidden: bool = False) -> pygame.Surface:
    image = effects.charge_icon(power)
    if hidden:  # a dark silhouette: the shape, never the colors
        image = pygame.mask.from_surface(image).to_surface(
            setcolor=rgba("px.floor.3", 255), unsetcolor=rgba("fx.none", 0)
        )
    return pygame.transform.scale_by(image, scale) if scale > 1 else image


def rarity_frame(screen: pygame.Surface, rect: pygame.Rect, rarity: str, token: str) -> None:
    """The card frame: plain for rare, notched corners for epic, four rays for legendary."""
    color = rgb(token)
    pygame.draw.rect(screen, color, rect, 1)
    if rarity == "epic":
        for cx, cy, dx, dy in (
            (rect.left, rect.top, 1, 1),
            (rect.right - 1, rect.top, -1, 1),
            (rect.left, rect.bottom - 1, 1, -1),
            (rect.right - 1, rect.bottom - 1, -1, -1),
        ):
            screen.fill(rgb("px.outline"), (min(cx, cx + 2 * dx), cy, 3, 1))
            screen.fill(rgb("px.outline"), (cx, min(cy, cy + 2 * dy), 1, 3))
            screen.fill(color, (cx + 2 * dx, cy + dy, 1, 1))
            screen.fill(color, (cx + dx, cy + 2 * dy, 1, 1))
    elif rarity == "legendary":
        for cx, cy, dx, dy in (
            (rect.left, rect.top, -1, -1),
            (rect.right - 1, rect.top, 1, -1),
            (rect.left, rect.bottom - 1, -1, 1),
            (rect.right - 1, rect.bottom - 1, 1, 1),
        ):
            for i in range(1, 4):
                screen.fill(color, (cx + dx * i, cy + dy * i, 1, 1))


# The hub ---------------------------------------------------------------------------------------


def draw_hub(screen, menu: Menu, session, ready: bool, message: str | None, sector: int) -> None:
    left, right, top = _frame(screen)
    title = "FUSE BOX" if menu.in_fuse_box else "PAUSED"
    context = f"SECTOR {sector} NEXT" if menu.in_fuse_box else f"SECTOR {sector}"
    _header(screen, title, context, left, right, top)
    world = session.campaign.world
    free = any(
        a in world.unlocked and b in world.unlocked and not owned_result(world.unlocked, a, b)
        for a, b in RECIPE_ORDER
    )
    for i, item in enumerate(menu.hub_items):
        y = top + 20 + i * 13  # room for six items (dev mode adds DEV) above the message
        chosen = i == menu.hub
        waiting = item == "CONTINUE" and not ready
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y - 2, 104, 12))
            hud.text(screen, ">", (left, y), "px.hazard.1")
        token = "px.floor.3" if waiting else ("ui.text" if chosen else "ui.dim")
        label = "QUIT? SPACE AGAIN" if item == "QUIT" and menu.quitting else item
        hud.text(screen, label, (left + 8, y), "px.lamp" if label != item else token)
        if item == "FUSE" and free:  # a free first roll is waiting
            screen.fill(rgb("px.rarity.legendary"), (left + 40, y + 2, 3, 3))
    # Right: what is equipped, always in view.
    rx = left + 116
    hud.text(screen, "EQUIPPED", (rx, top + 20), "ui.dim")
    for i, ability in enumerate(world.player.slots):
        y = top + 32 + i * 18
        card = pygame.Rect(rx, y, right - rx, 16)
        pygame.draw.rect(screen, rgb("px.wall.2"), card, 1)
        hud.key_glyph(screen, "QE"[i], card.x + 2, card.y + 2, "ui.text")
        if ability:
            screen.blit(_icon(ability), (card.x + 9, card.y + 5))
            hud.text(screen, NAMES[ability], (card.x + 19, card.y + 4), "ui.text")
            if ability in FUSED:
                hud.rarity_marks(screen, rarity_of(ability), card.right - 14, card.y + 7)
        else:
            hud.text(screen, "EMPTY", (card.x + 19, card.y + 4), "px.floor.3")
    if menu.in_fuse_box and not ready:  # its own line, under the equipped slots
        hud.text(screen, "ROUTING POWER...", (rx, top + 70), "px.floor.3")
    if menu.in_fuse_box and message:
        for i, line in enumerate(_wrap(message.upper(), 38)[:2]):
            hud.text(screen, line, (left, PANEL.bottom - 31 + i * 9), "px.lamp")
    _footer(screen, "W/S MOVE  SPACE PICK" + ("" if menu.in_fuse_box else "  TAB RESUME"), left)


# Loadout ---------------------------------------------------------------------------------------


def draw_loadout(screen, menu: Menu, session, tuning) -> None:
    left, right, top = _frame(screen)
    _header(screen, "LOADOUT", "ESC BACK", left, right, top)
    world = session.campaign.world
    rows = loadout_rows(world.unlocked)
    if not rows:
        hud.text(screen, "DESTROY ROBOTS TO STEAL", (left, top + 20), "ui.dim")
        hud.text(screen, "THEIR POWERS", (left, top + 30), "ui.dim")
    pick = min(menu.row, len(rows) - 1) if rows else -1
    first = max(0, min(pick - LOADOUT_ROWS + 1, len(rows) - LOADOUT_ROWS)) if rows else 0
    first = max(0, min(first, pick))
    for i, ability in enumerate(rows[first : first + LOADOUT_ROWS]):
        y = top + 16 + i * 12
        chosen = first + i == pick
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y - 2, 108, 12))
        screen.blit(_icon(ability), (left, y))
        hud.text(screen, NAMES[ability], (left + 10, y), "ui.text" if chosen else "ui.dim")
        if ability in FUSED:
            hud.rarity_marks(screen, rarity_of(ability), left + 94, y + 2)
        elif ability in world.player.slots:
            hud.text(
                screen,
                "QE"[world.player.slots.index(ability)],
                (left + 104, y),
                "ui.dim",
                "topright",
            )
    if first > 0:
        hud.text(screen, "^", (left + 50, top + 12), "ui.dim")
    if first + LOADOUT_ROWS < len(rows):
        hud.text(screen, "v", (left + 50, top + 16 + LOADOUT_ROWS * 12 - 3), "ui.dim")
    screen.fill(rgb("px.wall.1"), (left + 110, top + 14, 1, 92))
    rx = left + 116
    for i, ability in enumerate(world.player.slots):
        card = pygame.Rect(rx + i * 57, top + 15, 54, 16)
        pygame.draw.rect(screen, rgb("px.wall.2"), card, 1)
        hud.key_glyph(screen, "QE"[i], card.x + 2, card.y + 2, "ui.text")
        if ability:
            screen.blit(_icon(ability), (card.x + 9, card.y + 5))
            hud.text(screen, hud.SHORT[ability], (card.x + 18, card.y + 4), "ui.text")
    if pick >= 0:
        ability = rows[pick]
        y = top + 36
        screen.blit(_icon(ability, 2), (rx, y))
        hud.text(screen, NAMES[ability], (rx + 18, y), "ui.text")
        if ability in FUSED:
            rarity = rarity_of(ability)
            hud.rarity_marks(screen, rarity, rx + 18, y + 11)
            hud.text(screen, rarity.upper(), (rx + 32, y + 9), f"px.rarity.{rarity}")
        from overload.game.view import DESCRIPTIONS  # one table of descriptions

        for i, line in enumerate(_wrap(DESCRIPTIONS[ability], 19)[:3]):
            hud.text(screen, line, (rx, y + 20 + i * 9), "ui.dim")
        seconds = cooldown_of(ability, tuning) / TICK_RATE
        hud.text(screen, f"COOLDOWN {seconds:.1f} S", (rx, y + 49), "px.floor.3")
        if ability in INGREDIENTS:
            a, b = INGREDIENTS[ability]
            hud.text(screen, f"{a.upper()} + {b.upper()}", (rx, y + 58), "px.floor.3")
    _footer(screen, "W/S PICK  Q/E EQUIP  ESC BACK", left)


# Fuse ------------------------------------------------------------------------------------------


def draw_fuse(screen, menu: Menu, session) -> None:
    left, right, top = _frame(screen)
    _header(screen, "FUSE", "H HOW ROLLS WORK", left, right, top)
    world = session.campaign.world
    # The base powers, with their spare charges, and the two sockets.
    for i, power in enumerate(BASE_POWERS):
        box = pygame.Rect(left + i * 26, top + 15, 22, 22)
        stolen = power in world.unlocked
        socketed = power in menu.sockets
        token = "px.hazard.1" if i == menu.cursor else ("ui.text" if socketed else "px.wall.2")
        pygame.draw.rect(screen, rgb(token), box, 1)
        if i == menu.cursor:
            pygame.draw.rect(screen, rgb(token), box.inflate(2, 2), 1)
        icon = _icon(power, 2, hidden=not stolen)
        screen.blit(icon, icon.get_rect(center=box.center))
        spare = world.bank.get(power, 0)
        label = f"+{spare}" if stolen else "?"
        hud.text(screen, label, (box.centerx, box.bottom + 1), "ui.dim", "midtop")
    sx = left + 92
    for i in range(2):
        box = pygame.Rect(sx + i * 34, top + 15, 22, 22)
        pygame.draw.rect(screen, rgb("ui.dim"), box, 1)
        if i < len(menu.sockets):
            icon = _icon(menu.sockets[i], 2)
            screen.blit(icon, icon.get_rect(center=box.center))
    hud.text(screen, "+", (sx + 28, top + 22), "ui.text", "midtop")
    # The ROLL button: the last stop of the cursor.
    button = pygame.Rect(sx + 64, top + 18, right - sx - 64, 16)
    on = menu.cursor == len(BASE_POWERS)
    ready = len(menu.sockets) == 2 and menu.roll is None
    fill = "px.hazard.1" if on and ready else "px.wall.1"
    screen.fill(rgb(fill), button)
    pygame.draw.rect(screen, rgb("px.hazard.1" if on else "px.wall.2"), button, 1)
    label_token = "px.outline" if on and ready else ("ui.text" if ready else "px.floor.3")
    hud.text(screen, "ROLL", button.center, label_token, "center")

    # The three possible results.
    if len(menu.sockets) == 2:
        terms = roll_terms(session, *menu.sockets)
        _cards(screen, menu, terms, left, top + 47)
        _terms(screen, menu, terms, left, right, top + 104)
    else:
        for i, line in enumerate(
            (
                "PICK TWO POWERS TO SEE WHAT",
                "THEY CAN FUSE INTO: ONE RARE,",
                "ONE EPIC AND ONE LEGENDARY.",
            )
        ):
            hud.text(screen, line, (left, top + 52 + i * 10), "ui.dim")
        if menu.notice:
            hud.text(screen, menu.notice, (left, top + 104), "px.lamp")
    if menu.roll is not None and menu.roll.phase == "reveal":
        _reveal(screen, menu)
        _footer(screen, "Q / E EQUIP   SPACE DONE", left)
    elif menu.roll is not None:
        _footer(screen, "ROLLING...   SPACE SKIP", left)
    else:
        _footer(screen, "A/D MOVE  SPACE PICK  F ROLL  ESC BACK", left)
    if menu.help:
        _help(screen, session)


def _cards(screen, menu: Menu, terms: dict, left: int, y: int) -> None:
    roll = menu.roll
    for i, power in enumerate(terms["results"]):
        rarity = rarity_of(power)
        rect = pygame.Rect(left + 2 + i * (CARD_W + 6), y, CARD_W, CARD_H)
        seen = power in menu.discovered
        out = terms["guaranteed"] and rarity == "rare"
        screen.fill(rgb("px.floor.0"), rect)
        token = "px.floor.3" if out else f"px.rarity.{rarity}"
        rarity_frame(screen, rect, rarity, token)
        if roll is not None and roll.highlight == i:
            pygame.draw.rect(screen, rgb("px.hazard.1"), rect.inflate(4, 4), 2)
        hud.rarity_marks(screen, rarity, rect.x + 3, rect.y + 3)
        hud.text(screen, f"{terms['odds'][i]}%", (rect.right - 3, rect.y + 2), token, "topright")
        icon = _icon(power, 2, hidden=not seen)
        screen.blit(icon, icon.get_rect(midtop=(rect.centerx, rect.y + 12)))
        name = NAMES[power] if seen else "???"
        for j, line in enumerate(_wrap(name, 11)[:2]):
            hud.text(screen, line, (rect.centerx, rect.y + 29 + j * 9), "ui.text", "midtop")
        if power == terms["owned"] and roll is None:
            hud.text(screen, "OWNED", (rect.centerx, rect.bottom - 11), "px.hazard.1", "midtop")


def _terms(screen, menu: Menu, terms: dict, left: int, right: int, y: int) -> None:
    if menu.roll is not None:
        return  # the cards and the reveal say everything while a roll is shown
    if menu.notice:  # a notice takes the whole line, the meter comes back after
        hud.text(screen, menu.notice, (left, y), "px.lamp")
        return
    if terms["blocked"]:
        hud.text(screen, terms["blocked"], (left, y), "px.floor.3")
    elif terms["cost"]:
        a, b = menu.sockets
        cost = terms["cost"]
        text = f"REROLL: {cost} {a.upper()} + {cost} {b.upper()}"
        hud.text(screen, text, (left, y), "ui.text")
    else:
        hud.text(screen, "FIRST ROLL FREE", (left, y), "px.rarity.epic")
    # The guarantee meter: a pip per rare in a row, full means epic or better.
    if terms["guaranteed"]:
        hud.text(screen, "EPIC+ GUARANTEED", (right, y), "px.rarity.epic", "topright")
        return
    hud.text(screen, "LUCK", (right - 4 * terms["streak_max"] - 2, y), "ui.dim", "topright")
    for p in range(terms["streak_max"]):
        pip = pygame.Rect(right - 4 * (terms["streak_max"] - p) + 1, y + 2, 3, 3)
        if p < terms["streak"]:
            screen.fill(rgb("px.rarity.epic"), pip)
        else:  # an empty pip is hollow, not only darker
            pygame.draw.rect(screen, rgb("ui.dim"), pip, 1)


def _reveal(screen, menu: Menu) -> None:
    roll = menu.roll
    rarity = rarity_of(roll.result)
    box = pygame.Rect(0, 0, 150, 76)
    box.center = (PANEL.centerx, PANEL.centery + 4)
    screen.fill(rgb("px.outline"), box)
    rarity_frame(screen, box, rarity, f"px.rarity.{rarity}")
    if rarity == "legendary":  # an outline pulse, never a white flash
        pulse = (roll.clock // 200) % 2
        pygame.draw.rect(screen, rgb("px.rarity.legendary"), box.inflate(4 + 2 * pulse, 4), 1)
    icon = _icon(roll.result, 3)
    screen.blit(icon, icon.get_rect(midtop=(box.centerx, box.y + 6)))
    hud.text(screen, NAMES[roll.result], (box.centerx, box.y + 30), "ui.text", "midtop")
    hud.rarity_marks(screen, rarity, box.centerx - 22, box.y + 43)
    hud.text(screen, rarity.upper(), (box.centerx - 8, box.y + 41), f"px.rarity.{rarity}")
    if roll.replaced and roll.replaced != roll.result:
        line = f"REPLACES {NAMES[roll.replaced]}"
    elif roll.replaced:
        line = "ROLLED THE SAME AGAIN"
    else:
        line = "NEW POWER"
    hud.text(screen, line, (box.centerx, box.y + 55), "ui.dim", "midtop")


def help_lines(tuning) -> list[str]:
    rare, epic, legendary = percentages(tuning.fuse_odds)
    streak = tuning.fuse_guarantee_after
    cost = tuning.reroll_cost
    return [
        "HOW ROLLS WORK",
        "PICK TWO POWERS. EVERY PAIR CAN",
        "BECOME A RARE, AN EPIC OR A LEGENDARY.",
        f"ODDS: {rare}% RARE, {epic}% EPIC, {legendary}% LEGEND.",
        f"{streak} RARES IN A ROW: THE NEXT ROLL IS",
        "EPIC OR BETTER (THE LUCK PIPS).",
        "A PAIR'S FIRST ROLL IS FREE. A REROLL COSTS",
        f"{cost} SPARE CHARGE OF EACH (+N = SPARES).",
        "IT REPLACES WHAT YOU HAVE, FOR BETTER",
        "OR WORSE. A RUN'S LUCK IS SET BY ITS SEED.",
    ]


def _help(screen, session) -> None:
    box = PANEL.inflate(-8, -4)
    screen.fill(rgb("px.outline"), box)
    pygame.draw.rect(screen, rgb("px.rarity.epic"), box, 1)
    for i, line in enumerate(help_lines(session.campaign.tuning)):
        token = "ui.text" if i == 0 else "ui.dim"
        hud.text(screen, line, (box.x + 6, box.y + 3 + i * 11), token)
    hud.text(screen, "H OR ESC CLOSES", (box.right - 6, box.y + 3), "ui.dim", "topright")


# Controls --------------------------------------------------------------------------------------


def draw_controls(screen, menu: Menu) -> None:
    left, right, top = _frame(screen)
    _header(screen, "CONTROLS", "ESC BACK", left, right, top)
    for i, (action, key) in enumerate(CONTROLS):
        y = top + 16 + i * 10
        hud.text(screen, action, (left, y), "ui.dim")
        hud.text(screen, key, (right, y), "ui.text", "topright")
    _footer(screen, "ESC BACK", left)


def draw_dev(screen, menu: Menu) -> None:
    left, right, top = _frame(screen)
    _header(screen, "DEV", "NOT FOR PLAYTESTS", left, right, top)
    for i, (label, value) in enumerate(menu.dev.rows()):
        y = top + 15 + i * 10
        chosen = i == menu.dev_row
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y - 1, right - left + 4, 10))
        hud.text(screen, label, (left, y), "ui.text" if chosen else "ui.dim")
        if value:
            cycle = label in ("NEXT ROLL", "GRANT POWER")
            text = f"< {value} >" if cycle and chosen else value
            hud.text(screen, text, (right, y), "px.hazard.1", "topright")
    if menu.dev.notice:
        hud.text(screen, menu.dev.notice, (left, PANEL.bottom - 21), "px.lamp")
    _footer(screen, "W/S MOVE  A/D CHANGE  SPACE DO  ESC BACK", left)


def draw_menu(screen, menu: Menu, session, tuning, ready: bool, message, sector: int) -> None:
    if menu.screen == "hub":
        draw_hub(screen, menu, session, ready, message, sector)
    elif menu.screen == "loadout":
        draw_loadout(screen, menu, session, tuning)
    elif menu.screen == "fuse":
        draw_fuse(screen, menu, session)
    elif menu.screen == "dev":
        draw_dev(screen, menu)
    else:
        draw_controls(screen, menu)
