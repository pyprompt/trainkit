---
name: kenney-to-usd
description: Download official Kenney asset packs and convert supported static OBJ/palette models to textured USD files in this PyPrompt project. Use when asked to import, download, or regenerate Kenney 3D assets.
---

# Kenney assets to USD

## Scope and prerequisites

Use this skill for official `https://kenney.nl/assets/<slug>` packs.
The automation supports static OBJ files with same-stem MTL files containing
one white `colormap` material and `Textures/colormap.png` (as in Train Kit).
It is not a general FBX/GLB converter and does not support animation, multiple
materials, arbitrary textures, transparency or 2D packs. Unsupported archives
must be inspected and the converter extended; never silently omit materials.

Run in **this project's PyPrompt Python environment**, which supplies `requests`,
`usdkit`, and `src` on the import path. The script contains its own OBJ conversion
and zoo-generation helpers; it does not depend on the runtime showcase module.
It is project-local, not a standalone script for ordinary system Python; do not
attempt to install a guessed `usdkit` package from PyPI.

## Workflow

1. Confirm the requested pack URL and output directory. Inspect the asset page
   and license. Default destination: `assets/` relative to the working
   directory, with `models/`, `textures/`, and a reference-based `zoo.usda`.
   Existing matching USD files are regenerated, not skipped.
2. Run `scripts/convert.py` relative to this skill directory, as shown below.
   Prefer `--archive` when the official ZIP is already available.
3. If downloading, obtain the page's `data-download-id`, request a fresh URL
   from `https://kenney.nl/download-link/<id>`, then fetch the ZIP. Send the asset
   page as `Referer` plus a browser user-agent: missing headers can produce 403.
   Never hard-code an expiring signed URL, guess archive paths, or use unofficial
   mirrors to bypass download restrictions. Stop and report persistent failures.
4. The script preflights archive materials and filenames, copies `License.txt`,
   and writes `models/*.usd` with relative texture paths. It also writes
   `zoo.usda`, referencing all models in a bounds-spaced, Y-up grid.
   After all assets and zoo references validate, it removes the cached ZIP.
   It reads named ZIP members instead of extracting untrusted archive paths.
5. Each exported stage is reopened. The script checks the default prim, mesh,
   face-corner UV/normal counts, vertex indices, and texture file existence.
   Report the actual converted count and output path, not the page's advertised
   count. Train Kit currently contains 103 OBJ models.
6. If appearance matters, also inspect representative assets in a viewer;
   structural checks alone do not prove visual fidelity.

## Run in PyPrompt

Use the skill-script tool with skill `kenney-to-usd`, script `convert.py`, and
arguments `["https://kenney.nl/assets/train-kit", "--output", "assets"]`.
To reuse an existing ZIP without network access, add
`["--archive", "assets/kenney_train-kit.zip"]` to the arguments.

`--archive` reads the specified ZIP in place and preserves it; otherwise the script
reuses `<output>/kenney_<slug>.zip` or downloads it if missing, then deletes that
cached ZIP after successful conversion and validation. Existing unrelated files
are not deleted.
A failed conversion keeps the archive and can leave partial outputs; resolve the
reported problem and rerun before reporting completion.

## Conversion contract

- **USD only. Do not export USDZ** unless the user explicitly requests it.
- Preserve OBJ vertex positions, face winding, polygon topology, UVs and normals.
  OBJ groups are merged into one static mesh; separate object hierarchy is not
  preserved. Use face-varying UVs/normals and no subdivision. In `usdkit`,
  assign interpolation metadata directly as a string for both attributes:
  ```python
  attribute.metadata["interpolation"] = "faceVarying"
  ```
- Use a USD Preview Surface shader with the palette texture marked sRGB.
- Keep Y-up and original coordinates; interpret one source unit as one meter
  without rescaling. Confirm scale separately for packs with other conventions.
- Use a default `/Asset` Xform so each file can be referenced as an asset.
- Store shared palettes at `textures/colormap.png`, referenced from models as
  `../textures/colormap.png`. Distinct palettes use
  `textures/<slug>/<model>/colormap.png`. Keep the textures directory alongside
  the models directory when moving the collection.
- Generate `zoo.usda` with relative references, never flatten it. Use mesh bounds
  for nonoverlapping XZ grid cells, centered horizontally and grounded at Y=0.
- Retain the original license. Do not infer a license solely from the brand.
- No Git operations, deletion of old exports, or unrelated entry-point changes
  are part of this skill.

## Texture/UV troubleshooting

If a model renders with rainbow palette stripes instead of its intended colors:

1. Check that the palette matches the official archive, the relative texture path
   resolves, and the shader reads the mesh's `st` UV primvar.
2. Check that UV and normal interpolation metadata is `faceVarying`. Assign it
   directly as a string as shown above; explicit `usd.Typed` wrapping is unnecessary.
3. Repair missing or incorrect interpolation metadata by opening each stage,
   assigning `"faceVarying"` to `/Asset/Mesh` attributes `primvars:st` and `normals`,
   and saving the stage.
   This does not require changing UV values, splitting vertices, flipping axes,
   or replacing the palette. Keep the converter fixed as well so regeneration
   does not reintroduce the problem.
4. Reopen the saved stage and render it with `usdkit.StageComponent`; await
   `component.render(stage, entity)` before inspecting the scene. Recreate cached
   showcase scenes (restart the run if needed) rather than inspecting an old render.
   A successful render result and valid array counts alone do not prove correct
   texture mapping.

## Verification status

The script was tested offline against all 103 Train Kit OBJ models in a temporary
output directory: all USD stages reopened, referenced textures existed, and no
USDZ files were produced. The interpolation-token repair was also applied to all
103 project models and they passed structural validation. The saved
`train-diesel-a.usd` was visually verified through `StageComponent`: its
intended yellow-and-gray appearance replaced the rainbow stripes. This visual
check covers that representative model, not every asset. Other packs must pass
preflight and validation; their support is not implied by the Train Kit test.
