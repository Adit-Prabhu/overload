"""Session flow between the campaign, the rival selector and the Fuse Box. No pygame.

Per simulation tick:
- In an encounter: step the campaign and record what the Regulator could see. A retry
  restarts the observation record, because a retry reuses the encounter's entry checkpoint.
- When an encounter is cleared: send the summary to the selector (the live condition starts
  its one request here, the fixed schedule ignores it) and open the Fuse Box.
- In the Fuse Box: hold for MIN_FUSE_TICKS in every condition, poll the selector without
  blocking. The hold equals the request deadline, which starts at the same moment, so by the
  time any condition may continue the live reply has always arrived or been abandoned. The
  wait never reveals the condition.
`confirm` starts the next encounter with the frozen protocol.
"""

from __future__ import annotations

from overload.agent.client import DEADLINE_SECONDS
from overload.agent.observations import ObservationLog, observe_world
from overload.agent.selector import Selector
from overload.agent.tactics import Decision
from overload.session.trace import TraceWriter
from overload.sim.campaign import Campaign
from overload.sim.inputs import InputFrame
from overload.sim.powers import RECIPE_ORDER, RECIPES, Kit, fused_name
from overload.sim.tuning import TICK_RATE

MIN_FUSE_TICKS = round(DEADLINE_SECONDS * TICK_RATE)
FALLBACK_LINE = "Grid link unstable. Regulator running default protocol."


class Session:
    def __init__(
        self,
        campaign: Campaign,
        selector: Selector,
        trace: TraceWriter | None = None,
        session_id: str | None = None,
    ) -> None:
        self.campaign = campaign
        self.selector = selector
        self.trace = trace
        self.session_id = session_id
        self.log = ObservationLog(1)
        self.fuse_ticks = 0
        self.summaries: dict[int, dict] = {}
        self.decisions: dict[int, Decision] = {}
        first = selector.poll(1)
        if first is None or first.tactic != campaign.protocols[1]:
            raise ValueError("encounter 1 must start on the neutral protocol in every condition")
        self.decisions[1] = first
        self._trace_decision(first, None)
        # The run seed fixes every fusion roll, so analysis can line rolls up across sessions.
        self._trace(
            "encounter_start", encounter=1, protocol=campaign.protocols[1], seed=campaign.seed
        )

    # Simulation ticks ---------------------------------------------------------------------

    def tick(self, frame: InputFrame) -> None:
        campaign = self.campaign
        if campaign.stage == "encounter":
            encounter = campaign.encounter
            retries = campaign.retries[encounter]
            campaign.step(frame)
            if campaign.retries[encounter] != retries:
                self.log = ObservationLog(encounter)
                self._trace("retry", encounter=encounter, retries=campaign.retries[encounter])
                return
            observe_world(self.log, campaign.world)
            if campaign.stage != "encounter":
                self._encounter_cleared(encounter)
        else:
            campaign.step(frame)  # the Surge stands still in the Fuse Box while the menu is open
            if campaign.stage == "fuse_box":
                self.fuse_ticks += 1
                self.pending_decision()

    def _encounter_cleared(self, encounter: int) -> None:
        self._trace(
            "encounter_end",
            encounter=encounter,
            ticks=self.campaign.world.tick,
            retries=self.campaign.retries[encounter],
        )
        if self.campaign.stage == "ending":
            self._trace("ending", protocols=self.campaign.protocols)
            return
        summary = self.log.summary(self.campaign.protocols[encounter])
        self.summaries[encounter + 1] = summary
        self.selector.prepare(encounter + 1, summary)
        self.fuse_ticks = 0

    # Fuse Box ----------------------------------------------------------------------------

    def pending_decision(self) -> Decision | None:
        """The next encounter's decision once known. Never blocks."""
        upcoming = self.campaign.encounter + 1
        if upcoming not in self.decisions:
            decision = self.selector.poll(upcoming)
            if decision is not None:
                self.decisions[upcoming] = decision
                self._trace_decision(decision, self.summaries.get(upcoming))
        return self.decisions.get(upcoming)

    def ready(self) -> bool:
        return (
            self.campaign.stage == "fuse_box"
            and self.fuse_ticks >= MIN_FUSE_TICKS
            and self.pending_decision() is not None
        )

    def fuse_message(self) -> str | None:
        """The approved fallback line (D7), shown only in the live condition."""
        decision = self.decisions.get(self.campaign.encounter + 1)
        if self.selector.condition == "live" and decision and decision.source == "fallback":
            return FALLBACK_LINE
        return None

    def confirm(self) -> Decision | None:
        """Leave the Fuse Box. Returns the decision used, or None if not ready yet."""
        if not self.ready():
            return None
        decision = self.decisions[self.campaign.encounter + 1]
        waited = self.fuse_ticks - MIN_FUSE_TICKS
        self.campaign.begin_next(decision.tactic)
        self.log = ObservationLog(self.campaign.encounter)
        self._trace(
            "encounter_start",
            encounter=self.campaign.encounter,
            protocol=decision.tactic,
            extra_wait_ticks=waited,
        )
        return decision

    def _menu_encounter(self) -> int:
        """The encounter a loadout change applies to: the next one from the Fuse Box."""
        campaign = self.campaign
        return campaign.encounter + (1 if campaign.stage == "fuse_box" else 0)

    def equip(self, slot: int, ability: str) -> bool:
        ok = self.campaign.equip(slot, ability)
        self._trace("equip", encounter=self._menu_encounter(), slot=slot, ability=ability, ok=ok)
        return ok

    def fuse(self, a: str, b: str) -> str:
        """Fuse or reroll a pair. The trace logs every roll (which fusion of the run it was,
        the rarity, the charges spent, whether the guarantee applied) so analysis can account
        for luck. The rival never sees any of it."""
        campaign = self.campaign
        world, tuning = campaign.world, campaign.tuning
        recipe = RECIPES.get(frozenset((a, b)))
        n, streak, reroll = world.fusions, world.streak, recipe in world.unlocked
        result = campaign.fuse(a, b)
        fields: dict = {"encounter": self._menu_encounter(), "recipe": [a, b], "result": result}
        if result == "fused":
            fields.update(
                power=recipe,
                rarity=campaign.world.rarity[recipe],
                n=n,
                cost=tuning.reroll_cost if reroll else 0,
                guaranteed=streak >= tuning.fuse_guarantee_after,
            )
        self._trace("fuse", **fields)
        return result

    # Traces ------------------------------------------------------------------------------

    def _trace(self, event: str, **fields) -> None:
        if self.trace is not None:
            self.trace.write(event, session_id=self.session_id, **fields)

    def close(self) -> None:
        """Mark the end of the session in the trace, wherever the player stopped."""
        self._trace(
            "session_end",
            stage=self.campaign.stage,
            encounter=self.campaign.encounter,
            retries=self.campaign.retries,
        )

    def _trace_decision(self, decision: Decision, summary: dict | None) -> None:
        """Only the live condition sends a summary, so only it records one's hash."""
        if self.trace is not None:
            sent = summary if self.selector.condition == "live" else None
            self.trace.decision(decision, self.session_id, sent)


FUSE_NOTICES = {
    "fused": "FUSED. Q OR E EQUIPS IT",
    "missing": "STEAL BOTH POWERS FIRST",
    "unsupported": "STEAL BOTH POWERS FIRST",
    "no_charges": "NO SPARE CHARGES",
    "pick": "PICK A FUSION TO REROLL",
}


def next_recipe(kit, selected: str = "") -> tuple[str, str] | None:
    """The recipe F tries: the first one not fused yet whose ingredients are both stolen,
    else a reroll of the selected power if it is a fusion, else the first one not fused yet
    (it will report what is missing). None when every recipe is fused and no fusion is
    selected, so F never spends charges on a power the player did not pick."""
    open_recipes = [
        (a, b) for a, b in RECIPE_ORDER if RECIPES[frozenset((a, b))] not in kit.unlocked
    ]
    for a, b in open_recipes:
        if a in kit.unlocked and b in kit.unlocked:
            return a, b
    for a, b in RECIPE_ORDER:
        if RECIPES[frozenset((a, b))] == selected:
            return a, b
    return open_recipes[0] if open_recipes else None


class FuseBoxMenu:
    """The loadout and fusion menu. Keys: up and down pick a power, q and e equip it to
    that slot. Fuse makes the next recipe whose ingredients are both stolen. With none, it
    rerolls the selected fusion, else reports what the next recipe needs (see next_recipe).
    Rerolling an epic or legendary takes a second fuse press, since it can only lose.
    Returns each simulation-affecting action so the caller can record it for the replay."""

    def __init__(self) -> None:
        self.selected = 0
        self.notice: str | None = None
        self.last_result = ""
        self.armed: tuple[str, str] | None = None  # a reroll waiting for its second press

    def reset(self) -> None:
        self.selected = 0
        self.notice = None
        self.armed = None

    def press(self, session: Session, key: str) -> list | None:
        rows = session.campaign.world.unlocked
        armed, self.armed = self.armed, None  # any other key cancels a pending reroll
        if key in ("up", "down") and rows:
            step = -1 if key == "up" else 1
            self.selected = (self.selected + step) % len(rows)
            self.notice = None  # a new selection replaces the last notice
        elif key in ("q", "e") and rows:
            slot = 0 if key == "q" else 1
            ability = rows[min(self.selected, len(rows) - 1)]
            session.equip(slot, ability)
            self.notice = None
            return ["equip", slot, ability]
        elif key == "fuse":
            world = session.campaign.world
            selected = rows[min(self.selected, len(rows) - 1)] if rows else ""
            pair = next_recipe(Kit.from_world(world), selected)
            if pair is None:
                self.last_result = "pick"
                self.notice = FUSE_NOTICES["pick"]
                return None
            a, b = pair
            recipe = RECIPES[frozenset((a, b))]
            rarity = world.rarity.get(recipe, "rare")
            spare = all(world.bank.get(p, 0) >= session.campaign.tuning.reroll_cost for p in pair)
            if recipe in world.unlocked and rarity != "rare" and spare and armed != pair:
                self.armed = pair
                self.last_result = "confirm"
                self.notice = f"F AGAIN TO REROLL {rarity.upper()}"
                return None
            result = session.fuse(a, b)
            self.last_result = result
            self.notice = FUSE_NOTICES[result]
            if result == "fused":
                recipe = RECIPES[frozenset((a, b))]
                rarity = world.rarity[recipe]
                # short: it shares the footer line
                self.notice = f"{fused_name(recipe, rarity)} {rarity.upper()}"
            return ["fuse", a, b]
        return None
