"""Run the package to display one scene per asset family, with the zoo first."""

import asyncio
from typing import Any

from scenes import Entity, Scene
from views import Picker, VStack, View
import usdkit as usd

from trainkit import Asset, assets

SCENES: dict[str, Scene] = {}
RENDERS: dict[str, asyncio.Task[usd.RenderResult]] = {}
PICKERS: dict[str, Picker] = {}


def _render_finished(task: asyncio.Task[usd.RenderResult]) -> None:
    """Report background failures instead of leaving a silent blank scene."""
    if task.cancelled():
        return
    try:
        result: Any = task.result()
        if result.errors:
            print(f"USD render errors for {task.get_name()}: {result.errors}")
    except Exception as error:
        print(f"USD render failed for {task.get_name()}: {error}")


def scene_for(asset: Asset, variant: str | None = None) -> View:
    """Display an asset with a picker when it has multiple model variants."""
    loop = asyncio.get_running_loop()
    stage = asset.open(variant)
    name = asset.name if variant is None else f"{asset.name}-{variant}"
    entity = Entity(name)
    component = usd.StageComponent()
    entity.components.set(component)
    scene = Scene(entity)
    task = loop.create_task(component.render(stage, entity), name=name)
    task.add_done_callback(_render_finished)
    RENDERS[name] = task
    SCENES[name] = scene
    if len(asset.variants) == 1:
        return scene

    # Each picker edits and rerenders only its own scene's variant set.
    dynamic_stage: Any = stage
    model_variants = usd.VariantSet(dynamic_stage.default_prim, "model")

    def select_variant(value: str) -> None:
        if value not in asset.variants:
            raise ValueError(f"Unknown variant {value!r} for {asset.name!r}")
        model_variants.set_selection(value)
        previous = RENDERS[name]

        async def render_selection() -> usd.RenderResult:
            # Serialize renders: StageComponent does not automatically show edits.
            await asyncio.gather(previous, return_exceptions=True)
            return await component.render(stage, entity)

        task = loop.create_task(render_selection(), name=name)
        task.add_done_callback(_render_finished)
        RENDERS[name] = task

    picker = Picker(
        f"{asset.name} variant",
        options={value: value.replace("-", " ").title() for value in asset.variants},
        selection=asset.default_variant if variant is None else variant,
        on_change=select_variant,
    )
    PICKERS[name] = picker
    return VStack(picker, scene)


# Top-level scene values are available to PyPrompt when Run executes this file.
zoo = scene_for(assets["zoo"])
railroad_corner_large = scene_for(assets["railroad-corner-large"])
railroad_corner_small = scene_for(assets["railroad-corner-small"])
railroad_curve = scene_for(assets["railroad-curve"])
railroad_straight_bend_large = scene_for(assets["railroad-straight-bend-large"])
railroad_straight_bend = scene_for(assets["railroad-straight-bend"])
railroad_straight_bump_down = scene_for(assets["railroad-straight-bump-down"])
railroad_straight_bump_up = scene_for(assets["railroad-straight-bump-up"])
railroad_straight_hill_beginning = scene_for(assets["railroad-straight-hill-beginning"])
railroad_straight_hill_complete_half = scene_for(assets["railroad-straight-hill-complete-half"])
railroad_straight_hill_complete = scene_for(assets["railroad-straight-hill-complete"])
railroad_straight_hill_end = scene_for(assets["railroad-straight-hill-end"])
railroad_straight_skew_left_side = scene_for(assets["railroad-straight-skew-left-side"])
railroad_straight_skew_left = scene_for(assets["railroad-straight-skew-left"])
railroad_straight_skew_right_side = scene_for(assets["railroad-straight-skew-right-side"])
railroad_straight_skew_right = scene_for(assets["railroad-straight-skew-right"])
railroad_straight = scene_for(assets["railroad-straight"])
spline_segment = scene_for(assets["spline-segment"])
spline_track = scene_for(assets["spline-track"])
track = scene_for(assets["track"])
track_single = scene_for(assets["track-single"])
train_carriage_box = scene_for(assets["train-carriage-box"])
train_carriage_coal = scene_for(assets["train-carriage-coal"])
train_carriage_container = scene_for(assets["train-carriage-container"])
train_carriage_dirt = scene_for(assets["train-carriage-dirt"])
train_carriage_flatbed = scene_for(assets["train-carriage-flatbed"])
train_carriage_lumber = scene_for(assets["train-carriage-lumber"])
train_carriage_tank = scene_for(assets["train-carriage-tank"])
train_carriage_wood = scene_for(assets["train-carriage-wood"])
train_connector = scene_for(assets["train-connector"])
train_diesel = scene_for(assets["train-diesel"])
train_diesel_box = scene_for(assets["train-diesel-box"])
train_electric_bullet = scene_for(assets["train-electric-bullet"])
train_electric_city = scene_for(assets["train-electric-city"])
train_electric_double = scene_for(assets["train-electric-double"])
train_electric_square = scene_for(assets["train-electric-square"])
train_electric_subway = scene_for(assets["train-electric-subway"])
train_locomotive = scene_for(assets["train-locomotive"])
train_locomotive_passenger = scene_for(assets["train-locomotive-passenger"])
train_tram = scene_for(assets["tram"])

if __name__ == "__main__":
    print(f"Created {len(SCENES)} asset scenes; rendering in the background.")
