# Audio

**Purpose:** build the soundtrack and sound effects from one synth so everything sounds like one game.

**Read first:** `docs/ART_AND_AUDIO_DIRECTION.md` section 3 (music and sound effects), the audio event list.

**May:** write synth and song code in `tools/audio/`, render OGG files to `assets/audio/`, add manifest entries.

**May not:** use external samples or music generators without terms recorded in the manifest and Adit's approval. Never make an audio cue the only signal for a gameplay event.

**Output:** rendered audio, its source code, one preview file per batch, manifest entries.

**Handoff:** to Tech for integration and to QA for the mute check.

**Done when:** peaks are at or below -1 dBFS, loops are seamless, stems share one length, and every cue has a visual twin.

**Human approval:** Adit approves each listen-through.
