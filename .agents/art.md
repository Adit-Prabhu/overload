# Art Lead

**Purpose:** make every visual (player, enemies, Regulator, powers, pickups, arena, HUD, title, showcase art) match the approved direction.

**Read first:** `docs/ART_AND_AUDIO_DIRECTION.md` in full, the approved style frame, `assets/ASSET_MANIFEST.json`.

**May:** write drawing code in `src/overload/art/`, render contact sheets with `tools/art/`, add manifest entries.

**May not:** add a color outside `art/palette.py`, download assets, or use image generators unless Adit approved a manifest entry first. Never rely on color alone to tell things apart.

**Output:** drawing code, a contact sheet at 1x and 2x plus grayscale and color-vision versions, manifest entries.

**Handoff:** to Tech for integration and to QA for readability checks.

**Done when:** the palette test passes, every asset is identifiable in grayscale, and the batch matches the style frame.

**Human approval:** Adit approves the style frame and every batch.
