# References and attribution
Reviewed November 15, 2026. These are design references and intended dependencies, not an asset reuse license for commercial games.

| Source | Specific mechanic / material | What Overload borrows or changes | Terms / attribution |
| --- | --- | --- | --- |
| Nintendo, Kirby and the Forgotten Land, Copy Ability page | Copying enemy abilities and evolving Fire to Volcano Fire | Enemy-derived abilities and behavior-changing evolution. Overload uses drops, persistent session collection, two equipped powers and limited cross-type recipes | Proprietary reference. No game assets, screenshots, music or code copied. No reuse permission assumed |
| Supergiant Games, Hades, with PlayStation gameplay tips | Boons modifying attacks. Shield Special paired with a status-effect boon such as Curse of Pain | Active ability combinations in short encounters. Overload uses a shooter and a collection that persists within the session | Proprietary reference. No game assets, screenshots, music or code copied. No reuse permission assumed |
| Adit-Prabhu/abuse_remake | Observation boundary, Vertex response normalization, common manifest and replay/CI patterns | Reuse architecture concepts and adapt validated tooling to a rival selector. Original top-down gameplay | Student-authored repository inspected. No root reuse license found. Confirm authorship/permission before copying specific code. Original Abuse assets are excluded |
| Original prototype assets | Geometric placeholders and original text | Simple shapes communicate powers, enemy tells and hits | No external asset pack selected. Record creators and terms before adding external assets |

Links:
- https://www.nintendo.com/ph/switch/arzg/copy/index.html
- https://www.supergiantgames.com/games/hades/
- https://www.playstation.com/en-us/games/hades/tips-and-tricks-to-survive-your-first-hades-encounters/

Nintendo's Copy Ability page illustrates Fire evolving to Volcano Fire. PlayStation's Hades tips describe pairing the shield's Special with Curse of Pain (page opened and checked November 15, 2026).

GDF reader v2.1 Sections 5.1, 5.2, 3.5 and Gate 1 informed the document structure. No historical commercial GDD content was copied. No third-party game implementation code is included in this package.

The assistant helped propose scope, architecture, tests and this documentation. The human designer's preferences selected the action/collection/fusion direction and recurring rival. Implementation defaults remain recommendations until reviewed.

## Course and reuse sources
- GDF reader v2.1: https://github.com/columbia-university-ai-games/game-dev-f26/blob/main/docs/gdf.md (content SHA c8de4a8105f875dd9ef9b1ce4029adbf8d199770).
- Course stack/deployment guidance: https://github.com/columbia-university-ai-games/game-dev-f26/blob/main/README.md.
- Midterm inspected commit: https://github.com/Adit-Prabhu/abuse_remake/tree/ac1e2ba0a9b44b99a66a68c20102599591d7bbc1.
- Dated model-cost assumptions: `eval/configs/midterm.toml`, prices dated October 26, 2026. They are historical planning evidence, not a verified current tariff.
- Recorded midterm smoke latency: `EVALUATION.md`, p95 1.69 seconds for 20 calls. Overload's deployment and input differ, so this is a weak planning reference only.

Proposed dependencies: pygame-ce (LGPL v2.1), Cloudflare Agents SDK (MIT) and the chosen provider's service terms. Verify exact package LICENSE files and dependencies when pinning versions. Preserve notices and satisfy applicable distribution requirements. No dependency code is bundled in this documentation package. Use original art/audio and maintain an asset/license manifest before release.

Verified upstream dependency references:
- https://github.com/pygame-community/pygame-ce/blob/main/pyproject.toml
- https://github.com/cloudflare/agents/blob/main/LICENSE
