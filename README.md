# trainkit

Kenney's [Train Kit](https://kenney.nl/assets/train-kit), converted to USD.
The original asset license is in `assets/License.txt`.

## Browse the assets

In PyPrompt, press **Run** to execute `src/trainkit/__main__.py`. It displays the
zoo overview first, followed by one orbitable scene per asset family. Families
with multiple models have a picker above the scene; choosing a variant rerenders
that scene. For example, `train_tram` offers Classic, Modern, and Round.
Single-variant assets have no picker.

Scene creation uses PyPrompt's `scenes`, `views`, and `usdkit` modules and its
running event loop. Stages open synchronously, while `StageComponent` renders
in the background; render errors are printed. The entry point also keeps the
underlying scenes in `SCENES` and the pickers in `PICKERS`, keyed by asset name
(for example, `"tram"` or `"train-diesel"`). Running does not download or
convert assets.

## Use the catalog

`trainkit` exposes an `assets` mapping. Importing it builds the catalog without
creating scenes or scheduling render tasks:

```python
from trainkit import assets

tram = assets["tram"]
print(list(tram.variants))  # ['classic', 'modern', 'round']
print(tram.default_variant)
stage = tram.open("modern")

diesel_stage = assets["train-diesel"].open("b")
zoo_stage = assets["zoo"].open()
```

Each `open()` returns an independent USD stage. Omitting the argument selects
the asset's default; an unknown variant raises `ValueError`. Keep the returned
stage alive while using its prims. Catalog keys are generally hyphenated model
family names; the tram family is keyed as `"tram"`. `asset.variants` maps the
available variant names to their source model paths, and `asset.variant_layer`
points to the authored variant file for multi-variant families.

## Asset layout

```text
assets/
├── models/             # individual source .usd models
├── variants/           # reusable .usda files with model variant sets
├── textures/
│   └── colormap.png    # shared palette
├── zoo.usda            # reference-based grid overview
└── License.txt         # original CC0 license
```

Variant layers reference models using relative paths; models in turn reference
shared textures. Keep the directories together so those references resolve.
The zoo arranges the individual models on the XZ plane. Models retain their
original coordinates and Y-up orientation; one source unit is interpreted as one
meter, without rescaling.

## Regenerate source assets

Downloading and conversion belong to the project-local `kenney-to-usd` skill,
not the runtime package. See `.agents/skills/kenney-to-usd/SKILL.md`. The
converter writes the individual models, shared texture, and zoo; variant layers
are separate files under `assets/variants/`. The converter removes its cached
ZIP after successful validation; an explicit `--archive` input is preserved.
