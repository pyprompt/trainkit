"""Project-local Kenney OBJ/palette downloader and USD converter (PyPrompt)."""

import argparse
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zipfile import ZipFile

import requests
import usdkit as usd

from math import ceil, sqrt


def convert_obj(text: str, texture: Path, name: str) -> usd.Stage:
    """Preserve OBJ topology, face-varying normals, UVs and palette materials."""
    points: list[tuple[float, ...]] = []
    texcoords: list[tuple[float, ...]] = []
    normals: list[tuple[float, ...]] = []
    counts: list[int] = []
    indices: list[int] = []
    face_uvs: list[tuple[float, ...]] = []
    face_normals: list[tuple[float, ...]] = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        kind = fields[0]
        if kind == "v":
            points.append(tuple(float(v) for v in fields[1:4]))
        elif kind == "vt":
            texcoords.append(tuple(float(v) for v in fields[1:3]))
        elif kind == "vn":
            normals.append(tuple(float(v) for v in fields[1:4]))
        elif kind == "usemtl" and fields[1] != "colormap":
            raise ValueError(f"Unexpected material: {fields[1]}")
        elif kind == "f":
            counts.append(len(fields) - 1)
            for corner in fields[1:]:
                vertex, uv, normal = (int(value) for value in corner.split("/"))
                indices.append(vertex - 1 if vertex > 0 else len(points) + vertex)
                face_uvs.append(texcoords[uv - 1 if uv > 0 else len(texcoords) + uv])
                face_normals.append(normals[normal - 1 if normal > 0 else len(normals) + normal])
    if not counts:
        raise ValueError(f"No faces in {name}")
    stage: Any = usd.Stage()
    stage.up_axis = "Y"
    stage.meters_per_unit = 1.0
    root = stage.define_prim("/Asset", "Xform")
    root.display_name = name
    stage.default_prim = root
    mesh = stage.define_prim("/Asset/Mesh", "Mesh")
    mesh.make_attribute("points", "point3f[]", custom=False).set_value(points)
    mesh["faceVertexCounts"] = counts
    mesh["faceVertexIndices"] = indices
    mesh["subdivisionScheme"] = "none"
    mesh["normals"] = face_normals
    mesh.attribute("normals").metadata["interpolation"] = "faceVarying"
    uv_attr = mesh.make_attribute("primvars:st", "texCoord2f[]", custom=False)
    uv_attr.set_value(face_uvs)
    uv_attr.metadata["interpolation"] = "faceVarying"
    mesh["extent"] = [tuple(min(p[i] for p in points) for i in range(3)),
                      tuple(max(p[i] for p in points) for i in range(3))]
    material = stage.define_prim("/Asset/Material", "Material")
    shader = stage.define_prim("/Asset/Material/Surface", "Shader")
    shader["info:id"] = "UsdPreviewSurface"
    shader.make_attribute("inputs:roughness", "float", custom=False).set_value(0.8)
    shader.make_attribute("inputs:metallic", "float", custom=False).set_value(0.0)
    shader.make_attribute("outputs:surface", "token", custom=False)
    material.make_attribute("outputs:surface", "token", custom=False).connections = ["/Asset/Material/Surface.outputs:surface"]
    reader = stage.define_prim("/Asset/Material/UV", "Shader")
    reader["info:id"] = "UsdPrimvarReader_float2"
    reader.make_attribute("inputs:varname", "token", custom=False).set_value("st")
    reader.make_attribute("outputs:result", "float2", custom=False)
    sampler = stage.define_prim("/Asset/Material/Texture", "Shader")
    sampler["info:id"] = "UsdUVTexture"
    sampler.make_attribute("inputs:file", "asset", custom=False).set_value(usd.AssetPath(str(texture)))
    sampler.make_attribute("inputs:sourceColorSpace", "token", custom=False).set_value("sRGB")
    sampler.make_attribute("inputs:st", "float2", custom=False).connections = ["/Asset/Material/UV.outputs:result"]
    sampler.make_attribute("outputs:rgb", "float3", custom=False)
    shader.make_attribute("inputs:diffuseColor", "color3f", custom=False).connections = ["/Asset/Material/Texture.outputs:rgb"]
    mesh.apply_api_schema("MaterialBindingAPI")
    mesh.make_relationship("material:binding", custom=False).targets = ["/Asset/Material"]
    return stage


def write_zoo(root: Path) -> None:
    """Generate an unflattened grid overview with relative model references."""
    models = sorted((root / "models").glob("*.usd"))
    if not models:
        raise ValueError("No models to lay out.")
    bounds: list[Any] = []
    for path in models:
        stage: Any = usd.Stage.open(str(path))
        mesh = stage.prim("/Asset/Mesh")
        if mesh is None:
            raise ValueError(f"Missing asset mesh: {path}")
        bounds.append(mesh["extent"])
    columns = ceil(sqrt(len(models)))
    spacing_x = max(float(hi[0] - lo[0]) for lo, hi in bounds) + 1.0
    spacing_z = max(float(hi[2] - lo[2]) for lo, hi in bounds) + 1.0
    lines = ['#usda 1.0', '(', '    defaultPrim = "Zoo"',
             '    upAxis = "Y"', '    metersPerUnit = 1', ')', '',
             'def Xform "Zoo"', '{']
    for index, (path, (lo, hi)) in enumerate(zip(models, bounds)):
        name = "model_" + re.sub(r"[^A-Za-z0-9_]", "_", path.stem)
        x = (index % columns) * spacing_x - float(lo[0] + hi[0]) / 2
        y = -float(lo[1])
        z = (index // columns) * spacing_z - float(lo[2] + hi[2]) / 2
        lines.extend([
            f'    def Xform "{name}" (',
            f'        prepend references = @models/{path.name}@',
            '    )', '    {',
            f'        double3 xformOp:translate = ({x:.9g}, {y:.9g}, {z:.9g})',
            '        uniform token[] xformOpOrder = ["xformOp:translate"]',
            '    }',
        ])
    lines.append('}')
    path = root / "zoo.usda"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stage = usd.Stage.open(str(path))
    for model in models:
        name = "model_" + re.sub(r"[^A-Za-z0-9_]", "_", model.stem)
        if stage.prim(f"/Zoo/{name}/Mesh") is None:
            raise ValueError(f"Unresolved zoo reference: {model}")


def download(page_url: str) -> bytes:
    """Follow Kenney's public download flow using a fresh signed URL."""
    headers = {"Referer": page_url, "User-Agent": "Mozilla/5.0"}
    response = requests.get(page_url, headers=headers, timeout=60)
    response.raise_for_status()
    match = re.search(r"data-download-id=['\"]([0-9a-f]+)", response.text)
    if match is None:
        raise ValueError("No download ID found. Inspect the official asset page; do not guess a ZIP URL.")
    response = requests.get(
        f"https://kenney.nl/download-link/{match.group(1)}",
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()
    url = response.json().get("url")
    if not isinstance(url, str) or not url.startswith("https://kenney.nl/"):
        raise ValueError("Kenney did not return an official HTTPS download URL.")
    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()
    return response.content


def preflight(archive: ZipFile) -> list[str]:
    """Reject unsupported materials before writing converted assets."""
    models = sorted(n for n in archive.namelist() if n.lower().endswith(".obj"))
    if not models:
        raise ValueError("No OBJ models. This script does not convert FBX, GLB or 2D packs.")
    names: set[str] = set()
    for model in models:
        path = PurePosixPath(model)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", path.stem) or path.stem in names:
            raise ValueError(f"Unsafe or duplicate output name: {model}")
        names.add(path.stem)
        mtl_name = str(path.with_suffix(".mtl"))
        mtl = archive.read(mtl_name).decode("utf-8-sig")
        directives = [line.split() for line in mtl.splitlines()
                      if line.strip() and not line.lstrip().startswith("#")]
        expected = [["newmtl", "colormap"], ["Kd", "1", "1", "1"],
                    ["map_Kd", "Textures/colormap.png"]]
        if directives != expected:
            raise ValueError(f"Unsupported material in {mtl_name}; extend the converter rather than discarding materials.")
        archive.getinfo(str(path.parent / "Textures" / "colormap.png"))
        text = archive.read(model).decode("utf-8-sig")
        if f"mtllib {path.stem}.mtl" not in text.splitlines():
            raise ValueError(f"Unexpected OBJ material library: {model}")
    archive.getinfo("License.txt")
    return models


def validate(path: Path) -> None:
    """Reopen the saved USD and check mesh data and texture resolution."""
    stage: Any = usd.Stage.open(str(path))
    mesh = stage.prim("/Asset/Mesh")
    if mesh is None or stage.default_prim is None:
        raise ValueError(f"Missing mesh or default prim: {path}")
    indices = mesh["faceVertexIndices"]
    count = sum(mesh["faceVertexCounts"])
    if not count or not (count == len(indices) == len(mesh["normals"]) == len(mesh["primvars:st"])):
        raise ValueError(f"Invalid face-corner data: {path}")
    if min(indices) < 0 or max(indices) >= len(mesh["points"]):
        raise ValueError(f"Vertex index out of range: {path}")
    texture = stage.prim("/Asset/Material/Texture")["inputs:file"]
    if not (path.parent / texture.authored_path).is_file():
        raise ValueError(f"Missing texture: {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Official https://kenney.nl/assets/<slug> page")
    parser.add_argument("--output", type=Path, help="Asset directory; defaults to assets")
    parser.add_argument("--archive", type=Path, help="Use an existing ZIP without network requests")
    args = parser.parse_args(argv)
    match = re.fullmatch(r"https://kenney\.nl/assets/([a-z0-9-]+)/?", args.url)
    if match is None:
        parser.error("URL must be an official Kenney asset page.")
    slug = match.group(1)
    page = f"https://kenney.nl/assets/{slug}"
    root = (args.output or Path("assets")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive_path = args.archive or root / f"kenney_{slug}.zip"
    if args.archive is None and not archive_path.exists():
        data = download(page)
        # Check that the download is a ZIP before caching it.
        from io import BytesIO
        with ZipFile(BytesIO(data)) as check:
            preflight(check)
        archive_path.write_bytes(data)
    with ZipFile(archive_path) as archive:
        models = preflight(archive)
        output = root / "models"
        output.mkdir(exist_ok=True)
        (root / "License.txt").write_bytes(archive.read("License.txt"))
        for index, model in enumerate(models, 1):
            source = PurePosixPath(model)
            # Share identical palettes, but retain distinct textures for other packs.
            palette = archive.read(str(source.parent / "Textures" / "colormap.png"))
            texture = root / "textures" / "colormap.png"
            if texture.exists() and texture.read_bytes() != palette:
                texture = root / "textures" / slug / source.stem / "colormap.png"
            texture.parent.mkdir(parents=True, exist_ok=True)
            texture.write_bytes(palette)
            relative_texture = Path("..") / texture.relative_to(root)
            stage: Any = convert_obj(archive.read(model).decode("utf-8-sig"), relative_texture, source.stem)
            stage.default_prim.documentation = f"Kenney asset: {page}. See ../License.txt. Y-up; one source unit interpreted as one meter."
            path = output / f"{source.stem}.usd"
            stage.root_layer.export(str(path))
            validate(path)
            print(f"[{index}/{len(models)}] {path.name}")
    write_zoo(root)
    # Only clean up after every asset and the reference zoo have passed validation.
    # Explicit input archives belong to the caller; only remove our own cache.
    if args.archive is None:
        archive_path.unlink(missing_ok=True)
    print(f"Converted and validated {len(models)} USD assets in {output}")


if __name__ == "__main__":
    main()
