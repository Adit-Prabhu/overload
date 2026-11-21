"""Draws the menu (game/menu.py) at the view's 256 x 144: the hub, LOADOUT, FUSE with its
cards, spin and reveal, SETTINGS and CONTROLS. Rarity always shows by shape first (1, 2 or 3
cross marks and the card frame), then color (art direction, rarity tokens)."""

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
from overload.game.title import draw_rebind, draw_settings, rebind_footer, settings_footer
from overload.sim.fusions import INHERITS
from overload.sim.powers import (
    BASE_POWERS,
    EVOLUTIONS,
    FUSED,
    INGREDIENTS,
    NAMES,
    RECIPE_ORDER,
    cooldown_of,
    evolved,
    owned_result,
    rarity_of,
)
from overload.sim.tuning import TICK_RATE

PANEL = pygame.Rect(8, 6, 240, 132)
CARD_W, CARD_H = 72, 52

# Names for compact cards. The selected power's detail panel shows its full name.
_COMPACT_NAMES = {
    "bulwark": "BULW",
    "magnet": "MAG",
    "arc_trail": "TRAIL",
    "bolt_lance": "LANCE",
    "chain_jump": "JUMP",
    "shock_cone": "CONE",
    "shock_mine": "MINE",
    "storm_aura": "AURA",
    "impact_blink": "BLAST",
    "displacer": "SWAP",
    "static_guard": "STATIC",
    "tesla_coil": "COIL",
    "capacitor_armor": "ARMOR",
    "lodestone": "LODE",
    "ion_hook": "HOOK",
    "magrail": "RAIL",
    "bastion": "BAST",
    "reflector_wave": "WAVE",
    "fortress": "FORT",
    "vortex_cone": "VORTEX",
    "implosion": "IMPLO",
    "gravity_well": "WELL",
    "phase_guard": "PHASE",
    "afterimage": "DECOY",
    "undertow": "TOW",
    "grapple": "GRAP",
    "lightning_rod": "ROD",
    "shield_toss": "TOSS",
    "mirror_field": "MIRR",
}


def _power_label(ability: str, width: int) -> str:
    """Fit a power name in the available pixels beside its icon."""
    name = NAMES[ability]
    font = hud.pixel_font()
    if font.size(name)[0] <= width:
        return name
    label = _COMPACT_NAMES.get(ability, name)
    while label and font.size(label)[0] > width:
        label = label[:-1]
    return label


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def _wrap_px(text: str, max_px: int) -> list[str]:
    """Wrap words to fit inside `max_px` pixels in the HUD pixel font without truncating."""
    font = hud.pixel_font()
    lines: list[str] = []
    for word in text.split():
        if lines and font.size(f"{lines[-1]} {word}")[0] <= max_px:
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


def _footer(screen, text: str, left: int, token: str = "ui.dim") -> None:
    hud.text(screen, text, (left, PANEL.bottom - 11), token)


def _icon(power: str, scale: int = 1, hidden: bool = False) -> pygame.Surface:
    image = effects.charge_icon(power)
    if hidden:  # a dark silhouette: the shape, never the colors
        image = pygame.mask.from_surface(image).to_surface(
            setcolor=rgba("px.floor.3", 255), unsetcolor=rgba("fx.none", 0)
        )
    return pygame.transform.scale_by(image, scale) if scale > 1 else image


def _slot_key(screen, menu: Menu, slot: int, card: pygame.Rect) -> int:
    """The slot's bound key in its corner. Returns how far a longer label pushes the icon
    and name right."""
    label = menu.keys_page.binds.short(("power_q", "power_e")[slot])
    hud.key_glyph(screen, label, card.x + 2, card.y + 2, "ui.text")
    return 4 * (len(label) - 1)


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
    pulse = (pygame.time.get_ticks() // 400) % 2 == 0  # cosmetic only
    step = 11 if len(menu.hub_items) > 6 else 12
    for i, item in enumerate(menu.hub_items):
        y = top + 16 + i * step  # room for 7 items (dev mode adds DEV) above the fallback line
        chosen = i == menu.hub
        waiting = item == "CONTINUE" and not ready
        go = item == "CONTINUE" and ready  # pilot playtest: make the way on obvious
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y - 1, 104, step - 1))
            hud.text(screen, ">", (left, y), "px.hazard.1")
        token = "px.floor.3" if waiting else ("ui.text" if chosen else "ui.dim")
        if go:
            token = "px.hazard.1" if pulse else "ui.text"
        label = "QUIT? SPACE AGAIN" if item == "QUIT" and menu.quitting else item
        if go:
            label = "CONTINUE >>"
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
        shift = _slot_key(screen, menu, i, card)
        if ability:
            screen.blit(_icon(ability), (card.x + 9 + shift, card.y + 5))
            fused = ability in FUSED
            width = card.width - 19 - shift - (16 if fused else 2)
            label = _power_label(ability, width)
            hud.text(screen, label, (card.x + 19 + shift, card.y + 4), "ui.text")
            if fused:
                hud.rarity_marks(screen, rarity_of(ability), card.right - 14, card.y + 7)
        else:
            hud.text(screen, "EMPTY", (card.x + 19 + shift, card.y + 4), "px.floor.3")
    if menu.in_fuse_box:  # its own line, under the equipped slots
        if ready:
            hud.text(screen, "READY", (rx, top + 70), "px.hazard.1")
        else:
            hud.text(screen, "ROUTING POWER...", (rx, top + 70), "px.floor.3")
        _spares(screen, world, rx, top + 82)
    if menu.in_fuse_box and message:  # the live fallback line (never in dev mode)
        for i, line in enumerate(_wrap(message.upper(), 22)[:3]):
            hud.text(screen, line, (left, PANEL.bottom - 40 + i * 9), "px.lamp")
    keys = menu.keys_page.binds
    if menu.in_fuse_box and ready:
        prompt = f"SPACE ON CONTINUE: ENTER SECTOR {sector}"
        _footer(screen, prompt, left, "px.hazard.1" if pulse else "ui.text")
        return
    resume = "" if menu.in_fuse_box else f"  {keys.short('menu')} RESUME"
    _footer(screen, f"{keys.pair('up', 'down')} MOVE  SPACE PICK{resume}", left)


def _spares(screen, world, x: int, y: int) -> None:
    """Spare charges per stolen base power: what rerolls cost, and what each chassis pays
    (one of each, sim/floorplay.py). Every Fuse Box follows a chassis, so the +1 is always
    this visit's reward."""
    stolen = [p for p in BASE_POWERS if p in world.unlocked]
    if not stolen:
        return
    hud.text(screen, "SPARE CHARGES", (x, y), "ui.dim")
    for i, power in enumerate(stolen):
        cx = x + i * 22
        screen.blit(_icon(power), (cx, y + 12))
        hud.text(screen, str(world.bank.get(power, 0)), (cx + 9, y + 9), "ui.text")
    hud.text(screen, "+1 EACH: BOSS REWARD", (x, y + 20), "px.hazard.1")


# Loadout ---------------------------------------------------------------------------------------


def _evolution_pips(
    screen: pygame.Surface, power: str, count: int, total: int, x: int, y: int
) -> None:
    """Three square pips showing progress toward a base power's evolution. Square, so they
    stay distinct from the cross rarity marks on fused powers."""
    token = f"power.{power}"
    for p in range(total):
        pip = pygame.Rect(x + p * 4, y, 3, 3)
        if p < count:
            screen.fill(rgb(token), pip)
        else:
            pygame.draw.rect(screen, rgb("px.floor.3"), pip, 1)


def draw_loadout(screen, menu: Menu, session, tuning) -> None:
    left, right, top = _frame(screen)
    _header(screen, "LOADOUT", "ESC BACK", left, right, top)
    world = session.campaign.world
    rows = loadout_rows(world.unlocked)
    if not rows:
        # The left column ends at the divider (left + 110), so this wraps short.
        for i, line in enumerate(("DESTROY ROBOTS", "TO STEAL THEIR", "POWERS")):
            hud.text(screen, line, (left, top + 20 + i * 10), "ui.dim")
    pick = min(menu.row, len(rows) - 1) if rows else -1
    first = max(0, min(pick - LOADOUT_ROWS + 1, len(rows) - LOADOUT_ROWS)) if rows else 0
    first = max(0, min(first, pick))
    binds = menu.keys_page.binds
    font = hud.pixel_font()
    for i, ability in enumerate(rows[first : first + LOADOUT_ROWS]):
        y = top + 16 + i * 12
        chosen = first + i == pick
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y - 2, 108, 12))
        screen.blit(_icon(ability), (left, y))
        slot_label = (
            binds.short(("power_q", "power_e")[world.player.slots.index(ability)])
            if ability in world.player.slots
            else ""
        )
        slot_w = font.size(slot_label)[0] + 3 if slot_label else 0
        label = _power_label(ability, 80 - slot_w)
        hud.text(screen, label, (left + 10, y), "ui.text" if chosen else "ui.dim")
        if slot_label:
            hud.text(screen, slot_label, (left + 91, y), "px.hazard.1", "topright")
        if ability in FUSED:
            hud.rarity_marks(screen, rarity_of(ability), left + 93, y + 3)
        else:
            _evolution_pips(
                screen, ability, world.fragments.get(ability, 0), tuning.evolve_at, left + 93, y + 3
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
        shift = _slot_key(screen, menu, i, card)
        if ability:
            screen.blit(_icon(ability), (card.x + 9 + shift, card.y + 5))
            label = _power_label(ability, card.width - 20 - shift)
            hud.text(screen, label, (card.x + 18 + shift, card.y + 4), "ui.text")
    if pick >= 0:
        ability = rows[pick]
        y = top + 36
        screen.blit(_icon(ability, 2), (rx, y))
        hud.text(screen, NAMES[ability], (rx + 18, y), "ui.text")
        from overload.game.view import DESCRIPTIONS, EVOLVED_INFO  # one table of descriptions

        if ability in FUSED:
            rarity = rarity_of(ability)
            hud.rarity_marks(screen, rarity, rx + 18, y + 11)
            hud.text(screen, rarity.upper(), (rx + 32, y + 9), f"px.rarity.{rarity}")
            cy = y + 19
            for line in _wrap_px(DESCRIPTIONS[ability], right - rx):
                hud.text(screen, line, (rx, cy), "ui.dim")
                cy += 9
            seconds = cooldown_of(ability, tuning) / TICK_RATE
            hud.text(screen, f"COOLDOWN {seconds:.1f} S", (rx, max(cy + 2, y + 47)), "px.floor.3")
            a, b = INGREDIENTS[ability]
            hud.text(screen, f"{a.upper()} + {b.upper()}", (rx, max(cy + 11, y + 56)), "px.floor.3")
            inherited = INHERITS.get(frozenset((a, b)), ())
            if inherited:
                iy = max(cy + 20, y + 65)
                all_active = all(evolved(world.fragments, p, tuning) for p in inherited)
                prefix = "ACTIVE " if all_active else "USES "
                rect = hud.text(
                    screen, prefix, (rx, iy), "px.hazard.1" if all_active else "px.floor.3"
                )
                cx = rect.right
                for j, ingredient in enumerate(inherited):
                    if j > 0:
                        cx = hud.text(screen, " ", (cx, iy), "px.floor.3").right
                    active = evolved(world.fragments, ingredient, tuning)
                    tag = f"+{EVOLUTIONS[ingredient]}" if active else EVOLUTIONS[ingredient]
                    token = f"power.{ingredient}" if active else "px.floor.3"
                    cx = hud.text(screen, tag, (cx, iy), token).right
        else:
            frags = min(tuning.evolve_at, world.fragments.get(ability, 0))
            is_evolved = evolved(world.fragments, ability, tuning)
            _evolution_pips(screen, ability, frags, tuning.evolve_at, rx + 18, y + 11)
            if is_evolved:
                hud.text(screen, EVOLUTIONS[ability], (rx + 32, y + 9), f"power.{ability}")
                base_desc = DESCRIPTIONS[ability].split(". TWO MORE")[0]
                cy = y + 18
                for line in _wrap_px(base_desc, right - rx):
                    hud.text(screen, line, (rx, cy), "ui.dim")
                    cy += 8
                cy += 2
                for line in _wrap_px(EVOLVED_INFO[ability], right - rx):
                    hud.text(screen, line, (rx, cy), f"power.{ability}")
                    cy += 8
                seconds = cooldown_of(ability, tuning) / TICK_RATE
                hud.text(screen, f"COOLDOWN {seconds:.1f} S", (rx, cy + 3), "px.floor.3")
            else:
                hud.text(screen, f"EVOLVE {frags}/{tuning.evolve_at}", (rx + 32, y + 9), "ui.dim")
                cy = y + 19
                for line in _wrap_px(DESCRIPTIONS[ability], right - rx):
                    hud.text(screen, line, (rx, cy), "ui.dim")
                    cy += 9
                seconds = cooldown_of(ability, tuning) / TICK_RATE
                hud.text(
                    screen,
                    f"COOLDOWN {seconds:.1f} S",
                    (rx, max(cy + 2, y + 48)),
                    "px.floor.3",
                )
                hud.text(
                    screen,
                    f"AT {tuning.evolve_at}: {EVOLUTIONS[ability]}",
                    (rx, max(cy + 11, y + 57)),
                    "px.floor.3",
                )
    equip = binds.pair("power_q", "power_e")
    _footer(screen, f"{binds.pair('up', 'down')} PICK  {equip} EQUIP  ESC BACK", left)


# Fuse ------------------------------------------------------------------------------------------


def draw_fuse(screen, menu: Menu, session) -> None:
    left, right, top = _frame(screen)
    _header(screen, "FUSE", "H HOW ROLLS WORK", left, right, top)
    world = session.campaign.world
    # The base powers, with their spare charges, and the two sockets.
    for i, power in enumerate(BASE_POWERS):
        box = pygame.Rect(left + i * 24, top + 14, 20, 20)
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
        hud.text(screen, label, (box.centerx, box.bottom), "ui.dim", "midtop")
    sx = left + len(BASE_POWERS) * 24 + 8
    for i in range(2):
        box = pygame.Rect(sx + i * 34, top + 14, 20, 20)
        pygame.draw.rect(screen, rgb("ui.dim"), box, 1)
        if i < len(menu.sockets):
            icon = _icon(menu.sockets[i], 2)
            screen.blit(icon, icon.get_rect(center=box.center))
    hud.text(screen, "+", (sx + 27, top + 20), "ui.text", "midtop")
    # The ROLL button: the last stop of the cursor.
    button = pygame.Rect(sx + 62, top + 16, right - sx - 62, 16)
    on = menu.cursor == len(BASE_POWERS)
    ready = len(menu.sockets) == 2 and menu.roll is None
    if ready:  # a pair that cannot roll (not built yet, not stolen, no spare) is not ready
        ready = roll_terms(session, *menu.sockets)["can_roll"]
    fill = "px.hazard.1" if on and ready else "px.wall.1"
    screen.fill(rgb(fill), button)
    pygame.draw.rect(screen, rgb("px.hazard.1" if on else "px.wall.2"), button, 1)
    label_token = "px.outline" if on and ready else ("ui.text" if ready else "px.floor.3")
    hud.text(screen, "ROLL", button.center, label_token, "center")

    # The three possible results.
    if len(menu.sockets) == 2:
        terms = roll_terms(session, *menu.sockets)
        _cards(screen, menu, terms, left, top + 46)
        _terms(screen, menu, terms, left, right, top + 102)
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
            hud.text(screen, menu.notice, (left, top + 102), "px.lamp")
    if menu.roll is not None and menu.roll.phase == "reveal":
        _reveal(screen, menu)
        _footer(
            screen, f"{menu.keys_page.binds.pair('power_q', 'power_e')} EQUIP  SPACE DONE", left
        )
    elif menu.roll is not None:
        _footer(screen, "ROLLING...   SPACE SKIP", left)
    else:
        side = menu.keys_page.binds.pair("left", "right")
        _footer(screen, f"{side} MOVE  SPACE PICK  F ROLL  ESC BACK", left)
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
        screen.blit(icon, icon.get_rect(midtop=(rect.centerx, rect.y + 6)))
        name = NAMES[power] if seen else "???"
        for j, line in enumerate(_wrap(name, 11)[:2]):
            hud.text(screen, line, (rect.centerx, rect.y + 24 + j * 8), "ui.text", "midtop")
        if power == terms["owned"] and roll is None:
            hud.text(screen, "OWNED", (rect.centerx, rect.bottom - 12), "px.hazard.1", "midtop")


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
    box = pygame.Rect(0, 0, 198, 98)
    box.center = (PANEL.centerx, PANEL.centery - 2)
    screen.fill(rgb("px.outline"), box)
    rarity_frame(screen, box, rarity, f"px.rarity.{rarity}")
    if rarity == "legendary":  # an outline pulse, never a white flash
        pulse = (roll.clock // 200) % 2
        pygame.draw.rect(screen, rgb("px.rarity.legendary"), box.inflate(4 + 2 * pulse, 4), 1)
    icon = _icon(roll.result, 3)
    screen.blit(icon, icon.get_rect(midtop=(box.centerx, box.y + 4)))
    hud.text(screen, NAMES[roll.result], (box.centerx, box.y + 33), "ui.text", "midtop")
    marks_w = (("rare", "epic", "legendary").index(rarity) + 1) * 4 - 1
    rarity_label = rarity.upper()
    label_w = hud.pixel_font().size(rarity_label)[0]
    row_x = box.centerx - (marks_w + 4 + label_w) // 2
    hud.rarity_marks(screen, rarity, row_x, box.y + 46)
    hud.text(screen, rarity_label, (row_x + marks_w + 4, box.y + 44), f"px.rarity.{rarity}")
    from overload.game.view import DESCRIPTIONS  # one table of descriptions

    for i, line in enumerate(_wrap_px(DESCRIPTIONS[roll.result], box.width - 14)):
        hud.text(screen, line, (box.centerx, box.y + 56 + i * 9), "ui.text", "midtop")
    if roll.replaced and roll.replaced != roll.result:
        line = f"REPLACES {NAMES[roll.replaced]}"
        token = "px.hazard.1"
    elif roll.replaced:
        line = "ROLLED THE SAME AGAIN"
        token = "ui.dim"
    else:
        line = "NEW POWER"
        token = "ui.dim"
    hud.text(screen, line, (box.centerx, box.y + 80), token, "midtop")


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


# Settings and Controls -------------------------------------------------------------------------


def draw_settings_screen(screen, menu: Menu) -> None:
    left, right, top = _frame(screen)
    _header(screen, "SETTINGS", "AUDIO AND DISPLAY", left, right, top)
    page = menu.settings_page
    draw_settings(screen, page, left, right, top + 18)
    keys = menu.keys_page.binds
    token = "px.lamp" if page.notice else "ui.dim"
    footer = settings_footer(page, keys.pair("up", "down"), keys.pair("left", "right"))
    _footer(screen, footer, left, token)


def draw_controls(screen, menu: Menu) -> None:
    left, right, top = _frame(screen)
    _header(screen, "CONTROLS", "MOUSE AIMS AND FIRES", left, right, top)
    page = menu.keys_page
    draw_rebind(screen, page, left, right, top + 14)
    _footer(screen, rebind_footer(page, page.binds.pair("up", "down")), left)


def draw_dev(screen, menu: Menu) -> None:
    left, right, top = _frame(screen)
    _header(screen, "DEV", "NOT FOR PLAYTESTS", left, right, top)
    for i, (label, value) in enumerate(menu.dev.rows()):
        y = top + 14 + i * 9
        chosen = i == menu.dev_row
        if chosen:
            screen.fill(rgb("px.wall.1"), (left - 2, y, right - left + 4, 9))
        hud.text(screen, label, (left, y), "ui.text" if chosen else "ui.dim")
        if value:
            cycle = label in ("NEXT ROLL", "GRANT POWER")
            text = f"< {value} >" if cycle and chosen else value
            hud.text(screen, text, (right, y), "px.hazard.1", "topright")
    if menu.dev.notice:
        hud.text(screen, menu.dev.notice, (left, PANEL.bottom - 21), "px.lamp")
    keys = menu.keys_page.binds
    nav, side = keys.pair("up", "down"), keys.pair("left", "right")
    _footer(screen, f"{nav} MOVE  {side} CHANGE  SPACE DO  ESC BACK", left)


def draw_menu(screen, menu: Menu, session, tuning, ready: bool, message, sector: int) -> None:
    if menu.screen == "hub":
        draw_hub(screen, menu, session, ready, message, sector)
    elif menu.screen == "loadout":
        draw_loadout(screen, menu, session, tuning)
    elif menu.screen == "fuse":
        draw_fuse(screen, menu, session)
    elif menu.screen == "settings":
        draw_settings_screen(screen, menu)
    elif menu.screen == "dev":
        draw_dev(screen, menu)
    else:
        draw_controls(screen, menu)
