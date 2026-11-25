---
name: 3d-motion-infographic
description: Create narrated editorial infographics with real 3D meshes, measured camera moves, anchored labels and numbered photo references. Use for the 3D Motion Infographic style in this video pipeline.
---

# 3D Motion Infographic

Explain the user's subject through spatial relationships and visible changes. Build physical subjects from meshes with volume, materials and coherent illumination. A flat picture on a plane is appropriate for a photo inset or texture, not the main subject.

## Composition and appearance

- Fill the 1920×1080 stage with the scene. Use the complete height; do not reserve a bottom caption strip. Keep important text within 10% of the edges.
- Choose the environment from the topic: dark space for orbital scenes, daylight for outdoor scenes, neutral surroundings for technical cutaways. The default charcoal background is a starting point, not a requirement for every subject.
- Use one directional key light plus ambient fill, roughness appropriate to the material, and restrained highlights. Keep the direction consistent between shots. Preserve identifiable shapes, proportions and colors across phases.
- Use high contrast labels, normally white on dark surroundings, with a small colored rule or muted kicker. Labels explain a number, part or relationship; never print the spoken paragraph as subtitles. Titles: 48–64 px; labels: 28–36 px at 1080p.
- Project connector endpoints from mesh coordinates every frame. Anchor to the relevant surface or part, not the center of the screen. Keep connectors and labels clear of the subject silhouette.
- Photo insets occupy at most 38% of stage width, use contain sizing and a subtle border. Preserve the exact numbered reference and its aspect ratio. Place on the side with free space, usually upper right. Captions may identify the image but must not invent attribution or factual claims.

## Motion and speech

- The measured voiceover determines the phase duration. Use character alignment to anchor reveals to exact phrases with `cue`. Do not alter the speech or speech rate to fit animation.
- Prefer an establishing view, a gradual detail view and a final overview when the description requests them. Use camera position and lookAt keyframes with smooth easing for 2–5 second moves, or longer where narration needs it.
- Keep object motion slow enough to inspect. Use linear motion for continuous travel and smooth motion for deliberate camera moves. Continue subtle travel during a hold when the user describes it.
- Every transform must be an absolute function of timeline time. Seeking backwards must reproduce the same frame. Seed procedural detail. Never use a live animation loop or random changes to drive scene state.
- Keep reference-card reveals and text readable for the related spoken sentence. Do not add a dramatic effect, cut or extra claim absent from the input merely to fill time.

## Pipeline contract

The renderer consumes validated scene JSON, not executable AI JavaScript. Use named nodes with supported geometry, parent groups, material settings, camera keyframes, transform tracks and overlays. Times are seconds within the phase. Tracks interpolate absolute values and hold their end state.

Use `previewReady` to wait for texture decoding and shader preparation. Expose synchronous `renderAt(t)` for the web player and HyperFrames. Package the runtime and textures locally; never rely on a CDN while playing or exporting. A missing image, malformed plan or WebGL failure must be visible as an error.

## Example: orbital explanation

For the supplied Starlink description: make a sphere with Earth texture and a thin atmospheric edge, a satellite assembled from a metallic body and segmented blue solar panels, and a seeded distant star field. Establish Earth below left, approach the satellite, reveal the requested numbered photograph upper right, then pull out. Reveal the altitude connector and the user's label near the spoken altitude phrase. Preserve the satellite as a visible moving mesh throughout. This example does not prescribe the scene for other topics.
