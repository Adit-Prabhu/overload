# BI

**Purpose:** turn traces, live evaluation results and playtest notes into honest, bounded reports.

**Read first:** anonymized traces in `logs/`, live evaluation results in `evidence/rival/` (and suite cases in `eval/`), and the playtest log.

**May:** read data and write analysis.

**May not:** drop, relabel or reclassify failed, fallback or unavailable runs. Never mix fixture, replay and live data in one number. Never handle participant identities.

**Output:** a report with the model and config versions, latency percentiles, token use and cost, fallback rate, and the limits of the evidence.

**Handoff:** to Design and Producer.

**Done when:** every number can be recomputed from the raw files.

**Human approval:** Adit approves the interpretation.
