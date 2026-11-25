---
name: illustration-outlined-cartoon
description: >-
  Draws original hand-authored SVG spot illustrations in an outlined cartoon style for design and coding subjects. Identifying traits: a warm near-black ink outline on every flat fill in three weights (2.5 / 2 / 1.5 px), tapered ink slivers for folds, brows and finger splits, big-headed characters with huge white eyes, thick brows, open smiles and pink blush, blob hair with white highlight dashes, and a small decor set of "+" sparkle crosses, outline rings, squares and coloured dots on a transparent card. Covers one character with one hero prop, gripping and holding hands, sneakers, clothing folds and UI props. Use when someone asks for an outlined, inked, comic, sticker or doodle-style cartoon, a friendly character or mascot, or a spot illustration for an empty state, onboarding, 404 or error page, success state, blog header, feature spot or marketing card.
---

# Illustration: Outlined cartoon

A cheerful character illustration: one big-headed person in a lively pose, acting on one large hero prop, every shape flat-filled and ringed with hand-inked near-black line. It suits friendly product moments (success, onboarding, empty states) where a face and a gesture carry the message.
Use `illustration-bold-pop` instead for a dense, saturated object cluster with navy extrusions and hatching; `illustration-flat` when you want no outlines at all; `illustration-line-interior` for thin single-weight line, mostly white fills and realistic slim people in a wide room.

Extracted from a set of 42 original design-and-coding cards in 14 styles; the three cards in examples/ are this style's shipped cards.

## The look in one sentence
Every flat-filled shape sits inside a warm near-black ink line that varies by role (2.5 px silhouettes, 2 px parts, 1.5 px details), and every interior mark (folds, brows, finger and hair splits, white highlights) is a tapered sliver that swells in the middle and ends in two points, so the drawing reads as inked by hand, never as a uniform marker line.

## Palette
Measured from the three examples. Flat fills only.

| Role | Hex | Where it goes |
|---|---|---|
| Ink | `#1e1b1b` | every outline, pupils, brows, folds, code tokens, decor strokes. Never `#000` |
| White | `#ffffff` | eye whites, sneaker soles and toe caps, socks, screens, cards, highlight dashes, check ticks |
| Periwinkle / shade | `#6b7fd4` / `#4c5fb6` | hoodies, trousers, laptops, card headers, sneakers; shade only as fold slivers |
| Periwinkle pale / glass | `#c4ccf0` / `#dfe4f8` | secondary UI bars; lens glass tint (at fill-opacity 0.22) |
| Tomato red / shade | `#e5281d` / `#a9180f` | hair, tees, sneakers, trophy base, comment bubbles, grips |
| Warm yellow / shade | `#f6c343` / `#d99a1e` | trousers, trophies, blond hair, rims, poles, avatar dots |
| Leaf green / shade / light | `#4ea54a` / `#2f7f2c` / `#7cc777` | check badges, success buttons, paint |
| Blush pink / shade / light | `#f6a3b6` / `#dc7393` / `#fde0e5` | sweaters, avatar dots, tape, diff highlight rows |
| Skin salmon (+ crease, blush) | `#f5a39c` (`#d97e77`, `#ec7d78`) | light skin, cool |
| Skin peach (+ crease, blush) | `#fbd2c0` (`#e39c86`, `#f2898a`) | light skin, warm |
| Skin brown (+ crease, blush) | `#c97a5a` (`#9c5238`, `#e0625a`) | brown skin |
| Mouth / tongue | `#8a1b1b` / `#ec7d78` | open mouth fill, tongue |
| Dark hair | `#2b2525` | black hair (red `#e5281d` and yellow `#f6c343` hair are the other two) |
| Greys | `#b9b4c4`, `#d6d2df`, `#c9c6d6`, `#e6e3ee` | gutter dashes and label lines, dividers, shading on white garments, metal wire |
| Row tint | `#e3f2df` | approved/added rows in a code card |

The pencil wood `#f3d9a8` in Designer is the one deliberate off-palette tint; `lint --palette` warns on it.

- No background: the card is transparent and the page supplies white. No gradients, patterns, filters, opacity tricks or textures (the one exception is the 0.22 glass tint).
- Shade colours appear only as fold slivers or one small shadow band, never as big flat shadow shapes.
- One saturated colour per garment; give the hero prop a colour the clothes don't already use heavily (yellow trophy against a blue hoodie, green button against a red tee).

## Line and fill
All widths are final card px at 480 wide.
- **Outlines are strokes** on the filled shape, `stroke="#1e1b1b"`, `stroke-linejoin="round" stroke-linecap="round"`.
  - 2.5 px (`WO`): head, hair, torso, sleeves, trousers, shoes, the hero prop's silhouette.
  - 2.0 px (`W`): hands, cuffs, collars, necks, ears, small prop parts.
  - 1.5 px (`WI`): eye whites, screen insets, small inner panels. Fingers and thumbs 1.7–1.8.
  - Decor is unscaled: big "+" 2.0, small "+" 1.7 and 1.6, rings and squares 1.7, check badge 1.9, emphasis ticks 1.8.
- **Union outlines:** same-surface attachments (sleeve root at shoulder, pelvis to front leg, bare wrist to palm) share ONE outline: ink copies stroked at 2× the width underneath, then the fills on top (`union()` in the kit). A foreground arm crossing the coat is an OVERLAP, not a same-surface join: retain the inner contour of its elbow and forearm, leaving only the shoulder root open. Unioning the entire sleeve into the coat erases the arm. Paint coat details before the foreground sleeve, then its cuff and hand.
- **Folds are filled slivers, not strokes:** `fold(points, w)` swells to `w` and tapers to 0.35 px at both ends.
  - Clothing folds 1.3–1.9 px in ink or the garment's shade colour; brows 4.0 / 3.6; upper eyelid 2.0; nose hook 1.8; hair splits 1.4–1.5; finger splits 1.15; white highlight dashes 1.8–2.4.
  - Rib bands (hems, cuffs): vertical shade-colour slivers every 8 units, 1.3 px.
- Rods, cords and wires: an ink stroke 2×outline wider underneath, the colour stroke on top (`tubeStroke`).
- The scene is drawn in local units and scaled by 0.84 (`compose()`), so a stroke written as 2.5 appears in the file as 2.98. Never scale a group without dividing its stroke widths, or the weights drift.

## Characters
- **Proportions:** head with hair is about 37 % of standing height (code-review figure: hair top to sole 227 px, hair top to chin 85 px). Face 45 × 52 px. Short torso, short legs, round soft limbs.
- **Head:** a soft rounded box (`head()` in the kit), 3/4 turned toward the action, ears as 5 × 7.2 ellipses with an inner fold, a neck that narrows into the collar.
- **Eyes:** big white ellipses (near 6.2 × 7.4, far 5.4 × 7.0 local units), ink pupil r 3.7 / 3.4 with a white highlight r 1.25 up-right, a heavy upper-lid sliver 2.0. Glasses, when worn, are ink rings r 10 at 2 px.
- **Brows:** thick, tapered, 4.0 and 3.6 px. Thin brows were a judge note on the first card.
- **Mouth:** open, dark red fill with a tongue, outlined 1.9; a grin adds a white top-teeth band. Pink blush ellipses (4.8 × 2.8) under each eye, no outline.
- **Hair:** a scalloped blob (arcs between points, `hair()`), 2.5 outline, 2–3 white highlight dashes plus one white dot, and 3–5 split slivers in ink or the hair's shade. Buns and pencils behind the ear are hair accessories.
- **Hands** (follow references/craft.md for handedness, then check here):
  - Trace one continuous chain: shoulder → elbow → tapered forearm (about 12 → 10 local units) → narrower wrist → palm. Let the palm continue the forearm's direction; a smaller hand cannot fix a wrist that turns back on itself. Join bare forearm and palm without an outline across the wrist.
  - Block the palm as one rounded wedge before adding digits. Use ONE visible finger band with three or four soft bumps and at most three short, non-crossing separation slivers (1.15 px, about 2.5–2.8 units long). Do not draw another scalloped row or four knuckle creases on top; hidden fingers stay hidden.
  - The thumb's root has no outline across it: only its two sides and tip are inked, so it grows out of the palm.
  - Visible grip length about 0.6 × face width; compare the two hands against the same head at 1x. Start `fist()` near `k: 0.9–1.0` with the standard kit head; the legacy default `1.25` is often too large. Keep both hands at the same scale unless perspective explains a modest difference. `k` changes hand geometry, not ink weight or the rod's scene-space radius `rr`.
  - Also compare the palm mass with its OWN clothed forearm and cuff. An exposed support palm can look much larger than an edge-on grip even at the same numeric scale. Reduce the palm/fingers together when they dominate the arm, keep the forearm length, and rebuild the tapered wrist bridge; do not enlarge the arm to hide an oversized hand. Compensate ink and sliver widths when scaling.
  - Holding a flat object (laptop, tray): palm up under the base, finger band along the underside, thumb hooked over the front lip. A laptop balanced on fingertips was the first card's main fault.
  - Two hands: choose two contact patches on the prop FIRST and give each a role (control/grip, support/cradle, or push). Near hand on the rear grip and far hand farther along is a useful starting layout, not a handedness rule. Keep centres about 40+ local units apart for standard grips, then verify the actual silhouettes and thumbs leave a visible span of prop. Centre distance alone cannot prove clearance.
  - Reach: two 36-unit bones reach 72 local units. Place each wrist near its planned contact along the intended forearm/palm direction, then solve the arm; move the prop/contact or shoulder if the chain cannot reach. Inspect BOTH `elbow()` solutions. Aim for a small forearm-to-palm bend (roughly 30° or less as a starting point). A reachable wrist can still make a right-angle hook. Do not always choose an elbow below the shoulder–wrist line.
  - For an oblique approach, pass an explicit scene-space `wrist` to `fist()`; the kit joins it to a compact palm with a tapered bridge. Keep wrist-to-grip distance within `8*k–30*k` scene units (about 18–22 at `k: 0.95` is useful). Without `wrist`, the legacy template puts the wrist across the rod; `wristFromGrip()` exposes that position for planning. Neither mode chooses a good pose automatically.
  - `fist()` is a cylindrical wrap template. For a support under a broad object, draw a palm-up wedge below the base, one short finger band along the lip, and a thumb over it. For a push, draw the palm heel against the surface with grouped extended fingers. Do not paste a closed fist onto every contact; see [contact planning in craft.md](references/craft.md#contact-planning-and-arm-continuity).
  - Choose the visible hand silhouette before selecting a helper. A side wrap should show a rounded palm continuing from the wrist, a short thumb above the index, and two or three overlapping finger-edge lobes toward the front/lower edge. An under-support should show a smooth lower palm with grouped curved fingers rising around the near lip and a thumb hooking over the far/upper lip. Do not hide all fingers behind the palm or force both roles into the same vertical cuff-and-fist stamp. If `fist()` cannot represent the chosen view, hand-author this contour with kit paths, `union()` and `fold()`; preserve the contact layering.
- **Feet:** chunky sneakers about 40 local units long (`shoe()`): white sole 2.5, coloured upper 2.5, white toe cap, two white lace ticks, optional white ankle eyelet, one shade sliver at the heel; ankle socks (white or light pink) and rolled hems (23 units wide with one shade sliver).
- **Clothing:** hoodie (kangaroo pocket, white strings, hood band), sweater with rib hem and crew neck over collar points, tee, dungarees with bib, straps and yellow buttons. Folds at elbows, knees, crotch and the shaded side.
- **Poses that worked:** a leap with one fist raised (Awards), a lunge leaning 14° into a magnifier with both hands on the handle (Code Review), a braced push leaning back 5° on a long pole (Designer). Rotate the upper body as a group about the hip to lean; bend the knees; never stand bolt upright.

## Decor and props
- **One hero prop**, big: 35–50 % of the group's width (PR card 145 × 200 px, button pill 197 × 54 px, trophy 50 × 90 px). It carries the subject. Small UI inside it is abstract: rounded ink or colour bars (5.6 px ink lines, 4.4 px colour bars with a 1.15 outline), gutter dashes in `#b9b4c4`, check badges, avatar dots.
- **Decor set per card (7–9 marks):** one sparkle cluster (big "+" 17 px across at 2.0, small ones at (+16, −13) and (+15, +14) sized 6.8 and 5.6), 2–3 outline rings r 4.4–4.6, three filled dots (yellow r 3.6, blue r 3.4, red r 5.2–5.4), one outline square 10 × 10 rx 1.5 rotated 18°, optional green check badge r 7.6, optional three emphasis ticks at the action point.
- Put the sparkle cluster in the top corner opposite the heaviest mass; scatter the rest in the empty corners, 15–40 px clear of any contour.
- Never: ground lines, cast shadows, clouds, plants, background panels, speech text longer than two words.

## Composition
- Transparent 480 × 360 card. Whole group (figure, prop, decor) inside x 70–430, y 40–310: margins 40–48 px top, 50–58 px bottom, at least 50 px each side.
- Figure height 230–260 px standing (65–72 % of the card), about 200 px in a deep crouch. Figure on one side, hero prop on the other, joined by the action (the magnifier, the roller pole); the prop may overlap the figure's reach but not the face.
- Feet share one implicit baseline; no line is drawn.
- Group structure the examples use: `<g id="xx-card"><g id="xx-card-decor">…</g><g id="xx-card-scene" transform="translate(TX TY) scale(0.84)">…</g></g>` (`compose()`).

## Techniques
The kit `scripts/outline-kit.mjs` holds every repeated mark. Run its self-test from the skill folder: `node scripts/outline-kit.mjs demo.svg` (add `--proof` to paint thumbs red and index fingers blue). When changing kit geometry, also run `node --test scripts/outline-kit.test.mjs`; numeric tests supplement the contact zooms, not replace them.

```js
import * as K from '/abs/path/to/illustration-outlined-cartoon/scripts/outline-kit.mjs';
const { C, SKIN, W, WO, fold, limb, union, path, head, hair, dash, fist, shoe, hem, compose } = K;
// a tapered sleeve unioned with the torso: one silhouette, no seam
const arm = limb([[220, 178], [199, 190], [180, 200]], [24, 22, 19], 'round', 'flat');
scene.push(union([K.TORSO, arm], C.blue, WO));
// a fold: swells to 1.5 px, pointed ends
scene.push(fold([[187, 192], [181, 193.6], [175, 191.5]], 1.5));
```

A fist on a rod (`fist()`): plan the contact first, decide the hand from its shoulder, and verify the returned hand AND wrist after choosing the elbow.
```js
const v = K.unit(handleEnd, malletHead);         // along the handle, toward the business end
const c = plannedRearGrip;                     // on the prop, clear of the other hand
const k = 0.95;
// Example: wrist approaches a rear grip from the handle's rear/upper side.
// Adjust this offset with the pose; do not copy it onto every object.
const wrist = K.at(K.at(c, v, -20), K.perp(v), -3);
if (K.dist(shoulderN, wrist) >= 72) throw new Error('reposition the contact or shoulder');
// Compare both sides visually; this pose uses +1, not a universal elbow sign.
const e = K.elbow(shoulderN, wrist, 36, 36, 1);
const cuff = K.lerp(e, wrist, 0.42);
const h = fist({ c, v, elbow: e, from: cuff, wrist, rr: 5, k, view: 'back', ...SKIN.brown });
if (h.hand !== 'right') throw new Error('near arm of a figure facing right is the RIGHT hand');
if (K.dist(h.wrist, wrist) > 0.1) throw new Error('wrist/contact mismatch; re-plan');
const a = K.unit(e, wrist), b = K.unit(wrist, c);
if (a[0] * b[0] + a[1] * b[1] < Math.cos(Math.PI / 6)) throw new Error('wrist hooks; re-plan');
scene.push(h.behind, sleeve, rod, h.front, cuffBand);   // the cuff band goes last: in the back view the forearm is in `front`
```
`view: 'palm'` puts one curled finger band across the front of the rod; `view: 'back'` shows one palm mass with only a shallow peek of curled fingers. Thumb and index sit toward `v` in this template. For the legacy perpendicular approach, use `wristFromGrip(c, v, shoulder, k)`, omit the explicit `wrist` and verify the returned wrist again after IK: a later elbow on the opposite side can flip it. `gripFromWrist()` remains useful for a single free prop, but do not use it to slide two already planned contacts arbitrarily along a shared object. These helpers solve positions, not anatomy or contact occlusion.

Keep sleeve folds and prop details below the hand layers. At a contact, draw only the visible contour of each surface: do not carry the rod outline, cuff seam or thumb-root line through the palm. In a temporary proof, colour the thumb red and index blue, then count one thumb and one finger group per hand at 8x and at 1x.

For a hose, cable or long handle near the torso, sketch the WHOLE route before layering. A held section in front of the waist needs a continuous visible connection around the hip; draw that run over the clothing and under the gripping fingers. Do not leave its rear section behind the coat and restart its front section inside the shirt silhouette: this reads as penetration. If the prop genuinely passes behind a limb, show clear entry/exit overlaps consistent with the same route.

Union outline by hand, when you don't use the kit:
```xml
<path d="M…torso…" fill="#1e1b1b" stroke="#1e1b1b" stroke-width="5" stroke-linejoin="round"/>
<path d="M…sleeve…" fill="#1e1b1b" stroke="#1e1b1b" stroke-width="5" stroke-linejoin="round"/>
<path d="M…torso…" fill="#6b7fd4"/><path d="M…sleeve…" fill="#6b7fd4"/>
```

## Failure modes
- **Line reads as a uniform marker.** Every interior mark was a round-capped stroke of one width. Use `fold()` slivers and the three outline weights.
- **Weak, generic face.** Brows were thin lines; draw them as 3.6–4.0 px tapered slivers with a heavy upper lid.
- **Decor reads as noise.** Marks were sprinkled evenly. Group them: one sparkle cluster, then a few rings, dots and one square in the empty corners.
- **Prop balanced on fingertips.** A laptop sat on the fingertips; hold flat objects from below with the thumb over the lip.
- **Thumb on the wrong side.** A designer rejected a whole pass of hands for this. Decide left/right and palm/back per craft.md, use `fist()` and check its `hand`, then render a `--proof`-style copy at 8×.
- **Mitten or pasted-on fist.** No forearm taper, no wrist, no finger splits. Build cuff → forearm → palm → finger band → thumb.
- **Seam lines where parts join.** Sleeves outlined separately from the torso. Union same-colour shapes.
- **Knee notches.** Two separate trouser tubes overlapping at the crotch. Union the pelvis with the front leg; outline the back leg on its own behind it.
- **Weights drift after scaling.** A group was scaled without dividing its stroke widths. Use `compose()` or divide by the scale.
- **Thumb root outlined across the palm.** A closed thumb shape drew a seam over the hand; ink only its sides (`fist()` does this).
- **Hooked wrist despite valid IK.** Reach passed, but the forearm entered a grip at nearly 90°. Compare both elbow solutions and the forearm-to-palm direction; reposition the contact or torso if neither works.
- **Extra fingers from doubled contours.** Two scalloped rows, a rod line through the fingers, or a cuff/fold painted over the hand created false digits. Keep one finger group and remove hidden contours before adding detail.
- **Arm disappears into the coat.** A blanket torso/sleeve union removed a foreground overlap edge, or coat details were painted over the sleeve. Restore the bent elbow and inner forearm contour, then paint the cuff and hand in front. Joint coordinates and lint passing do not prove the arm is visible.
- **Two fists merge into one blob.** Check outlined silhouettes, including thumbs, as well as the 40+ centre spacing. Move the contacts apart or change one hand to a support pose.
- **Arms can't reach, hands float.** A planned contact was forced onto an unreachable arm. Keep the contact role, but reposition the prop, grip or shoulder and rebuild the chain; do not stretch the forearm or detach the wrist.
- **Hidden subject.** A squashed bug drawn under a mallet head vanished at 1x. Let anything pinned under a prop poke out at least 40 % on the open side, away from feet and other contours.
- **Decor lost or stray.** Decor is drawn first, under the scene, so a dot placed under a prop disappears; emphasis ticks fanned onto a prop read as stray scratches. Check each mark is in clear space.

## Examples
- `examples/awards.svg`: leaping figure in hoodie and glasses, laptop held palm-up from below, trophy raised in a fist; front-facing head, red blob hair, motion ticks under the jump.
- `examples/code-review.svg`: brown-skinned figure lunging with a magnifier held in two fists, a big PR card with diff rows, check badges and a red comment bubble; the lens magnifies the card under a clip path.
- `examples/designer.svg`: blond figure with bun and pencil braced against a long roller pole painting a green "Sign up" button, dashed outline for the unpainted part, drips, paint tray and taped swatches; two grip views on one pole.

## Workflow
Commands run from the skill folder (Playwright must resolve: `npm i -D playwright-core` there or globally).
1. **Brief:** name the subject and the one gesture that shows it. Pick the hero prop and what it shows at 1x.
2. **Pose:** decide the lean and near arm. On the prop, mark each contact and its role before drawing arms. Record LEFT/RIGHT, PALM/BACK, finger direction and what passes in front (references/craft.md).
3. **Block:** write a generator next to your card (`card.gen.mjs`) that imports the kit by absolute path. Place the prop contacts, hip pivot, ground y and shoulders; choose wrists close to the contacts along the palm's intended approach (or use `wristFromGrip()` for a perpendicular cylindrical grip), compare both IK elbows, then place ankles. Print contact/shoulder/elbow/wrist points, each returned `hand`, reach, wrist bend and hand clearance. Reposition the pose when constraints fail.
4. **Draw** back to front: far arm, legs and shoes, torso group (rotated about the hip), head, prop, near arm, hands, then decor in card px. `compose({ id: 'xx-subject', label, decor, scene, TX, TY })`.
5. **Render:** `node scripts/render.mjs card.svg card.png`.
6. **Sheet:** `node scripts/render.mjs --sheet sheet.png examples/*.svg card.svg`. Ask "same hand, same set?".
7. **Zoom:** `node scripts/render.mjs card.svg z-hand.png --zoom x,y,w,h --scale 8` for every hand, the face, both shoes and every contact. Make a thumb-proof copy (`fist({ …, proof: true })`) and zoom it. Check one palm, one thumb, at most four implied fingers, natural wrist entry and a visible span between hands. Lint cannot judge these visual/anatomical checks.
8. **Critique** against the five criteria in references/craft.md, harshly. At 1x, trace BOTH arms visually into their separate hands and compare the actual hand silhouettes with the requested contact/reference. A buried arm, an unreadable finger group or the wrong grip role is a failed render even when every numeric check passes. Fix and re-render. Expect 3–4 rounds.
9. **Lint:** `node scripts/lint.mjs card.svg --prefix xx- --palette style.json`. Only deliberate one-offs may warn.

## Verify
- [ ] Every filled shape has an ink `#1e1b1b` outline; no shape is outline-only except decor rings, the square and dashed guides.
- [ ] Three outline weights are visible: silhouettes heavier than hands, hands heavier than eye whites.
- [ ] Folds, brows, hair splits and finger splits are tapered slivers with pointed ends (zoom 8× on one).
- [ ] Brows are thick (3.6–4 px) and the eyes are white ellipses with a pupil and a white highlight.
- [ ] Pink blush ellipses with no outline sit under the eyes; the mouth is open with a tongue.
- [ ] Hair is a scalloped blob with at least two white highlight dashes.
- [ ] Each hand: cuff, tapering forearm, palm, finger band with short splits, thumb on the side craft.md requires (proof render checked).
- [ ] Each shoulder–elbow–wrist–palm chain is continuous, reachable and free of a hooked wrist; both hands use comparable body-relative scale.
- [ ] Both arm gestures and hand silhouettes read at 1x; foreground sleeve overlap edges remain visible, and curved finger shapes have visible skin area rather than black slits.
- [ ] Two-hand contacts have explicit roles and separate silhouettes; no rod, cuff or fold contour creates an extra digit or crosses a palm.
- [ ] Each palm is proportionate to its own forearm/cuff at 1x; the whole prop route reads continuously, with no unexplained endpoint inside clothing.
- [ ] Same-colour joins (sleeve to torso, pelvis to leg) show no seam line.
- [ ] Sneakers have a white sole and toe cap; trousers end in rolled hems.
- [ ] Exactly one sparkle cluster (big + two small); 7–9 decor marks in total, none touching a contour or hidden under a prop.
- [ ] No ground line, shadow, gradient, texture or background rect.
- [ ] Group inside x 70–430, y 40–310; figure 230–260 px tall; the subject reads at 1x.
- [ ] `lint.mjs --palette style.json` passes with only deliberate warnings.
