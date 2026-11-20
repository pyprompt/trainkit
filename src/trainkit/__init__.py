"""Train-kit assets, grouped into model families with selectable USD variants.

Importing the package only builds the catalog; it never creates scenes or tasks.
Use ``assets["train-diesel"].open("b")`` to get an independent USD stage.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import usdkit as usd

# PyPrompt can execute this file directly without defining __file__.
_source_file = globals().get("__file__")
ROOT = (
    Path(_source_file).resolve().parents[2] if _source_file else Path.cwd()
) / "assets"


@dataclass(frozen=True)
class Asset:
    """A model family whose source models compose as a USD variant set."""

    name: str
    variants: Mapping[str, Path]
    default_variant: str = "standard"
    variant_layer: Path | None = None

    def open(self, variant: str | None = None) -> usd.Stage:
        """Create a fresh stage, selecting a variant without affecting other users."""
        selection = self.default_variant if variant is None else variant
        if selection not in self.variants:
            raise ValueError(
                f"Unknown variant {selection!r} for {self.name!r}; "
                f"choose from {', '.join(self.variants)}"
            )
        # USDKit exposes these properties dynamically, outside its static stubs.
        stage: Any = usd.Stage(self.name)
        stage.up_axis = "Y"
        stage.meters_per_unit = 1
        root = stage.define_prim("/Asset", "Xform")
        stage.default_prim = root
        if self.variant_layer is not None:
            if not self.variant_layer.is_file():
                raise FileNotFoundError(self.variant_layer)
            root.references.add(str(self.variant_layer))
            root.variant_sets["model"].set_selection(selection)
            return stage
        variants = root.variant_sets.add("model")
        for name, path in self.variants.items():
            if not path.is_file():
                raise FileNotFoundError(path)
            variants.add(name)
            variants.set_selection(name)
            with variants.edit_target():
                root.references.add(str(path))
        variants.set_selection(selection)
        return stage


def _family(name: str) -> tuple[str, str]:
    """Group railroad finishes/ramps and named train/track alternatives."""
    if name.startswith("train-tram-"):
        return "tram", name.removeprefix("train-tram-")
    if name.startswith("railroad-"):
        parts = name.split("-")
        style = "damaged" if "damaged" in parts else "rail" if "rail" in parts else "standard"
        parts = [part for part in parts if part not in ("damaged", "rail")]
        if parts[-1] == "ramp":
            parts.pop()
            style += "-ramp"
        return "-".join(parts), style
    for suffix in (
        "-a", "-b", "-c", "-blue", "-green", "-red",
        "-damaged", "-detailed", "-large", "-wood",
    ):
        if name.endswith(suffix) and name != "train-carriage-wood":
            return name.removesuffix(suffix), suffix[1:]
    return name, "standard"


def _catalog() -> Mapping[str, Asset]:
    """Keep the zoo first and retain every source model as a family variant."""
    groups: dict[str, dict[str, Path]] = {}
    for path in sorted((ROOT / "models").glob("*.usd")):
        name, variant = _family(path.stem)
        group = groups.setdefault(name, {})
        if variant in group:
            raise ValueError(f"Duplicate variant {variant!r} in {name!r}")
        group[variant] = path
    catalog: dict[str, Asset] = {
        "zoo": Asset("zoo", MappingProxyType({"standard": ROOT / "zoo.usda"})),
    }
    for name, variants in groups.items():
        default = "standard" if "standard" in variants else next(iter(variants))
        layer = ROOT / "variants" / f"{name}.usda" if len(variants) > 1 else None
        catalog[name] = Asset(name, MappingProxyType(variants), default, layer)
    return MappingProxyType(catalog)


assets = _catalog()


def greet(name: str) -> str:
    return f"Hello, {name}!"
