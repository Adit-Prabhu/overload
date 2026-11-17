"""Session flow between the campaign, the rival selector and the Fuse Box. No pygame.

Per simulation tick:
- In an encounter: step the campaign and record what the Regulator could see. A retry
  restarts the observation record, because a retry reuses the encounter's entry checkpoint.
- When an encounter is cleared: send the summary to the selector (the live condition starts
  its one request here, the fixed schedule ignores it) and open the Fuse Box.
- In the Fuse Box: wait at least MIN_FUSE_TICKS in every condition, so a live request's wait
  does not reveal the condition, and poll the selector without blocking.
`confirm` starts the next encounter with the frozen protocol.
"""

from __future__ import annotations

from overload.agent.observations import ObservationLog, observe_world
from overload.agent.selector import Selector
from overload.agent.tactics import Decision
from overload.session.trace import TraceWriter
from overload.sim.campaign import Campaign
from overload.sim.inputs import InputFrame
from overload.sim.tuning import TICK_RATE

MIN_FUSE_TICKS = 2 * TICK_RATE
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
        self._trace("encounter_start", encounter=1, protocol=campaign.protocols[1])

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
            rival = campaign.world.rival
            if rival is not None:
                observe_world(self.log, campaign.world, (rival.x, rival.y))
            if campaign.stage != "encounter":
                self._encounter_cleared(encounter)
        elif campaign.stage == "fuse_box":
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

    # Traces ------------------------------------------------------------------------------

    def _trace(self, event: str, **fields) -> None:
        if self.trace is not None:
            self.trace.write(event, session_id=self.session_id, **fields)

    def _trace_decision(self, decision: Decision, summary: dict | None) -> None:
        if self.trace is not None:
            self.trace.decision(decision, self.session_id, summary)
