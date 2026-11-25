---
name: 3d-technical-illustration
description: Create realistic technical illustrations and layered educational animations that reveal how physical objects work, using cutaways, material detail, anchored labels and synchronized narration. Use for the 3D Technical Illustration style in this project's PNG/SVG pipeline.
---

# 3D Technical Illustration

Explain a physical mechanism through recognizable parts, spatial relationships and visible operation. Use detailed raster illustrations with believable volume, metallic surfaces and consistent lighting. This style uses layered PNG artwork in the existing SVG renderer; camera changes are planned views and transitions between illustrations.

## Appearance and clarity

- Work at 1920×1080. Let the subject occupy the frame; keep important labels inside a 7% margin. Do not reserve a narration strip or print spoken paragraphs.
- Choose surroundings from the scene: daylight and scenery outdoors, pale neutral space for component inspection. The preset background is a technical studio default, not a replacement for requested scenery.
- Preserve the selected object's silhouette, proportions, material colors, ports and connection points between every view.
- Use soft illumination from upper left, readable metallic highlights, restrained contact shadows, dark rubber and distinguishable copper windings or circuit boards. Do not add decorative glow around isolated components.
- Show only enough cutaway to explain the mechanism. Distinguish the housing, fixed parts and moving parts. Do not imply that an entire stator or gearbox housing rotates with its rotor or gears.
- Set Vietnamese labels as SVG text, typically 28–36 px, with a short leader line ending on the relevant part. Do not bake labels, borders, titles, logos or reference-card backgrounds into reusable artwork.

## Plan the layers before drawing

List each independently animated part and its local canvas, pivot, visible bounds and attachment points. Generate it separately from its housing. Keep shared geometry and scale across poses; a wider pose must not shrink the entire object.

Typical assemblies include a chassis under an independently fading body shell, wheels pivoting at their hubs, a rotor inside a fixed stator, gears inside a stationary casing, or a cable whose plug meets a declared socket. These are examples, not required subjects.

Foreground PNGs require actual transparent alpha and transparent margins. Background PNGs fill the stage. Generate each asset and pose from its screenplay description, with independently moving parts in separate layers. Inspect the result before relying on it; a successful PNG decode does not prove a correct cutout or alignment.

## Motion and explanation

- Use absolute-time transforms and opacity with the existing seekable SVG/CSS pipeline. Transitions, rotation and flow must reproduce the same frame after a backward seek.
- Build camera motion from nested scene groups. Use a separate pose/view for a change in perspective; avoid stretching a side elevation to simulate a true orbit.
- Keep fixed assemblies stationary while their moving parts rotate. During a cutaway, reveal an aligned interior layer beneath the shell rather than fading the entire assembly into empty space.
- For wheels, measure the visible hub and tyre bounds rather than assuming the PNG canvas center is the pivot. Normalize oval artwork to a circular assembly, keep the tyre silhouette and brake hardware stable, and rotate only a concentric rim with transparent spoke openings. Match angular speed to road travel; inspect a full revolution for wobble.
- For meshing gears, use precise SVG involute profiles with a shared module and pressure angle. Set center distance from the pitch radii, align a tooth with the mating space, and derive opposite angular velocities from the integer tooth counts. Do not scale the same raster gear to make different sizes. Keep metallic textures inside the precision silhouette and verify contact throughout a complete revolution.
- Draw energy flow, thermal circuits and connectors as SVG overlays anchored in the assembly's coordinate system. Their direction and visibility must agree with the explanation.
- Use measured narration duration and phrase cues for reveals. Preserve supplied speech, and split long explanations at sentence boundaries to meet the existing 120-second scene limit.

## PNG pipeline

Reuse the project's image-motion renderer, image generation, style loader and snapshot publication. Generate PNG assets and poses from the screenplay, using the existing size and alpha validation and image cache.

Package the PNGs, SVGs, HTML player and narration locally. Verify the first, middle and final frames of each scene, plus cutaway and connection transitions. Check alignment, label placement and reverse seeking in a browser before calling the preview complete.
