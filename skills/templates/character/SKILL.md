---
name: character
description: Generate consistent illustrations of Xeko, the recurring YouTube brand mascot, using character references, poses, and themed variants.
---

# Xeko Character Template

## Purpose

Xeko is the recurring brand mascot used in educational videos,
historical storytelling, science, technology, comedy, and
general entertainment content.

Every illustration featuring Xeko must preserve his recognizable
visual identity across different scenes and roles.

## Reference Directories

- `design/`: Original views and costume/identity variants, including new AI designs stored directly here.
- `poses/`: Facial expressions, states, gestures, and actions, including new AI poses stored directly here.
- `asset_catalog.json`: Canonical views, generated poses/costumes and extraction provenance.
- `template.json`: Character identity and generation configuration.

All reference paths are relative to this template directory.

## Character Identity

Character name: Xeko

Core appearance:

- Young male cartoon mascot.
- Large angular black spiky hair.
- Three prominent forward-facing hair spikes.
- Large round or oval white eyes.
- Small black pupils.
- Light peach skin.
- Simple rounded facial features.
- Small nose.
- Expressive mouth.
- Subtle pink cheeks.
- Large head and compact body.
- Thick black outlines.
- Playful and humorous personality.

## Default Outfit

- Bright red hoodie.
- White play-button emblem on the chest.
- Dark charcoal shorts.
- White socks.
- Red and white sneakers.
- Dark crossbody bag.

The default outfit may be replaced when the scene requires
a specific costume or historical role.

## Immutable Identity

Always preserve:

1. Signature black spiky hairstyle.
2. Recognizable head shape.
3. Characteristic eye design.
4. Original skin tone.
5. Cartoon body proportions.
6. Overall facial identity.
7. Consistent outline and rendering style.

Do not replace Xeko with another character.

Do not change his hair to pink, yellow, or another color unless
explicitly requested.

Do not add an extra ear behind the head in profile views.

## Reference Priority

Use references in the following order:

1. Original character design from `design/`.
2. Relevant themed costume from `design/`, selected through the asset catalog.
3. Relevant expression, state or action from `poses/`, selected through the asset catalog.
4. Scene-specific instructions.
5. General style configuration.

The four original views listed below are the highest-priority visual identity
references. Generated images in the same directory do not override them.

Pose and variant references must not override the core identity.

## Reference Selection

### Design

Always select at least one original design reference.

Choose the viewing angle that best matches the requested scene:

- Front view: `design/01-front-view.png`.
- Left profile (left side visible, facing right): `design/02-left-profile.png`.
- Right profile (right side visible, facing left): `design/03-right-profile.png`.
- Back view: `design/04-back-view.png`.

Inspect the image content and `asset_catalog.json` tags before deciding a view
is missing. Filenames are labels; their language is not evidence that an image
cannot be reused. A background extraction reuses an existing view.

### Poses

Select a relevant pose based on the scene's emotion and action.

Examples:

- Explaining: presenting, pointing, holding a board.
- Comedy: laughing, confused, embarrassed.
- Horror: frightened, shocked, trembling.
- Conflict: angry, frustrated, suspicious.
- Technology: typing, gaming, using a laptop.
- Everyday life: eating, running, sleeping, waving.

Use pose references as guidance rather than rigid limitations.

### Variants

Select a themed variant when the scene requires a different
profession, costume, historical role, or fictional identity.

Examples:

- Science: scientist or doctor.
- Technology: robot or hacker.
- History: king, knight, samurai, or strategist.
- Mystery: detective, fortune teller, or Taoist priest.
- Sports: football player.
- Fantasy: wizard or swordsman.
- Fiction: Pinocchio-inspired costume.

If a matching variant does not exist, create a new costume
while preserving Xeko's original identity.

## Character Transformation

Allowed changes:

- Clothing.
- Costumes.
- Hats and helmets.
- Props and accessories.
- Facial expressions.
- Body poses.
- Camera angles.
- Context-specific effects.
- Historical and fictional roles.

Special transformations are allowed when required by the story:

- Robot body.
- Pinocchio-style long nose.
- Superhero costume.
- Monster costume.
- Historical armor.
- Magical effects.

Even during transformations, preserve recognizable Xeko
features wherever visually possible.

## Historical and Fictional Roles

When portraying a famous historical or fictional character,
use Xeko as a mascot dressed in that role.

For example:

- Xeko dressed as Zhuge Liang.
- Xeko dressed as Pinocchio.
- Xeko dressed as a samurai.
- Xeko dressed as a football player.

Do not replace Xeko's face with the face of the referenced
historical or fictional character.

## Scene Integration

- Match the expression to the narration.
- Match the costume to the subject.
- Use appropriate props to explain concepts visually.
- Keep the character readable at small sizes.
- Allow full-body, half-body, portrait, and close-up framing.
- Avoid repetitive poses across consecutive scenes.
- Use supporting characters only when required.
- Do not automatically include Xeko in every scene.

## Anatomy Rules

- Maintain natural cartoon anatomy.
- Keep limbs attached correctly.
- Avoid duplicated arms and legs.
- Avoid extra fingers and facial features.
- In side views, show only the anatomically visible ear.
- Do not add floating ears behind the head.
- Preserve the signature hair silhouette.

## Prompt Construction

Build the image prompt using:

1. Character identity.
2. Selected design reference.
3. Costume or variant.
4. Expression and action.
5. Props.
6. Scene and environment.
7. Camera framing.
8. Visual style.
9. Identity and anatomy constraints.

## Prompt Example

Xeko, the recurring cartoon mascot with angular black spiky
hair, large round eyes, light peach skin, and compact cartoon
body, dressed as an ancient Chinese strategist, wearing blue
and white traditional robes and holding a feather fan,
confident humorous expression, explaining a historical
battle, expressive 2D cartoon illustration, thick black
outlines, bright flat colors, preserve original Xeko identity.

## Quality Checklist

Before accepting an illustration, verify:

- Is the character recognizable as Xeko?
- Is the original black spiky hairstyle preserved?
- Are the face and body proportions consistent?
- Does the costume match the scene?
- Does the expression match the narration?
- Are the anatomy and viewing angle correct?
- Are there any extra ears or duplicated body parts?
- Is the illustration visually clear?
- Is the selected visual style maintained?

Reject or regenerate illustrations that significantly alter
the character's core identity.

## Production asset library

Read `asset_catalog.json` before generating any pose. Exact matches are reused.
Search the original views, all images in `design/`, and existing `poses/` first.
Save new AI expressions, states, gestures and actions directly in `poses/`.
Save original views and new costume/identity variants directly in `design/`.
An image whose main purpose is an expression or action belongs in `poses/`;
an image introducing a new outfit or character design belongs in `design/`.
Do not create `transparent/`, generated-pose or costume subdirectories.

For a missing action or variant:

1. Inspect the nearest canonical design and matching pose/costume.
2. Generate only the missing static character sprite. Keep moving props,
   background, speech labels and scene effects as independent assets.
3. Request genuine transparent alpha. Preserve white interior eyes, shoes and
   play emblem. Do not remove all white pixels indiscriminately.
4. Review hair silhouette, face, outfit, body proportions, ears and limbs.
5. Save the PNG using a descriptive English filename directly in its category:
   `poses/xeko-happy-seated.png` for a pose, or
   `design/xeko-athlete-sweating.png` for an athletic outfit variant. Preserve
   the original reference. Append its path, category, tags, reference and
   generation provenance to `asset_catalog.json` and `generation_prompts.json`.
6. Copy the accepted asset into the consuming preview and keep a local catalog.

For a background extraction, keep the same category as the original and use a
`-transparent` filename suffix, for example `design/xeko-left-profile-transparent.png`
or `poses/xeko-surprised-transparent.png`. Record `derived_from` with the original
image path. This is an alpha derivative of the existing view or pose, rather
than a new pose or character identity. Preserve the original image.
For placement, measure the visible alpha silhouette and retain the same
character anchor during expression changes. Never shrink wider poses just
to give them the same bitmap dimensions.

The example `preview_xeko/tools/build.py` copies assets from this catalog on
each build, then creates a standalone HTML player and HyperFrames scenes.
