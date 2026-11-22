#!/usr/bin/env python3
"""Stamp the version through HexiumDistrib, validate both stores' rules, and pack the release zip (BlightedHeart).
Ported from MagicRunicMod tools/fold.py (the Runic playbook, owner 2026-11-22), plus the PDB rule (owner 2026-11-20): the
matching portable PDB ships as plugins/BlightedHeart.pdb, checked with libs-Tools/pdb_match.py (same GUID, no home path).

Merged port of two shipped folds (Rule 0):
  * TerroritySmellatory tools/fold.py - run by the csproj after EVERY build, so the package on disk is never a
    build behind the DLL; forward-slash entry names (backslashes make BepInEx see no plugins folder); fixed
    timestamps so unchanged inputs give a byte-identical zip; LICENSE staged into the dist folder.
  * BarrkUI fold-packages.py - THE RELEASE RULE (the user, 2026-10-18): a release (plain X.Y.Z) is ONE zip uploaded
    unchanged to Hexium AND Thunderstore, so it must pass both stores' rules (name [A-Za-z0-9_]+, plain version,
    description <= 250 chars, 256x256 icon, dependencies that exist on both). An alpha/beta/rc is Hexium-only.
    A release zip that already exists is FROZEN (never rebuilt without --force: an uploaded version is frozen,
    bump the version instead). Pre-release zips are rebuilt on every build.
The plugin's own version (BlightedHeartPlugin.PluginVersion) stays plain X.Y.Z; a pre-release tag lives in the manifest only.

Usage (run by hand at the release gate):
  python3 -I tools/fold.py --version 1.2.0 --dist HexiumDistrib --dll bin/Release/net48/BlightedHeart.dll
  python3 -I tools/fold.py ... --force        rebuild a frozen release zip
"""
import argparse
import os
import subprocess
import hashlib
import json
import pathlib
import re
import shutil
import sys
import zipfile

NAME = "BlightedWorldHeart"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
ENTRIES = ["manifest.json", "README.md", "CHANGELOG.md", "LICENSE.md", "icon.png", "plugins/BlightedHeart.dll", "plugins/BlightedHeart.pdb"]
MAX_DESCRIPTION = 250
PRE_RELEASE = re.compile(r"(alpha|beta|rc)\.[1-9][0-9]*")
# README schema v3 (libs-Tools/README-SCHEMA-v3.md): the store README is FORGED from README.src.md on every fold, as
# ThunderFeet's fold-package.py does. Badges are fetched only with RUNIC_CHECK_BADGES=1 (network).
ROOT = pathlib.Path(__file__).resolve().parent.parent
FORGE = pathlib.Path(os.environ.get("LIBS_TOOLS", ROOT.parent / "libs-Tools")) / "readme-forge" / "forge_readme.py"


def forge_readme(dist: pathlib.Path) -> bool:
    src = ROOT / "README.src.md"
    if not src.exists() or not FORGE.exists():
        print(f"fold: cannot forge the README ({'no README.src.md' if not src.exists() else 'no ' + str(FORGE)})")
        return False
    cmd = [sys.executable, "-I", str(FORGE), str(src), str(dist / "README.md"),
           "--manifest", str(dist / "manifest.json"), "--code-root", str(ROOT)]
    if os.environ.get("BH_CHECK_BADGES") == "1":
        cmd.append("--check-badges")
    else:   # say so: an unchecked badge must never read like a checked one (studio rule: NOT ASSESSED, 2026-11-17)
        print("fold: README badges NOT ASSESSED (set BH_CHECK_BADGES=1 to fetch and check them; do it before an upload)")
    return subprocess.run(cmd).returncode == 0


def stamp_manifest(path: pathlib.Path, version: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("version_number") != version:
        data["version_number"] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"fold: manifest version_number -> {version}")
    return data


def stage_licence(dist: pathlib.Path) -> None:
    src = dist.parent / "LICENSE.md"
    dest = dist / "LICENSE.md"
    if src.exists() and (not dest.exists() or dest.read_bytes() != src.read_bytes()):
        shutil.copy2(src, dest)
        print("fold: staged LICENSE.md")


def stage_dll(built: pathlib.Path, dist: pathlib.Path) -> pathlib.Path:
    staged = dist / "plugins" / built.name
    staged.parent.mkdir(parents=True, exist_ok=True)
    for src in (built, built.with_suffix(".pdb")):
        dst = dist / "plugins" / src.name
        if src.exists() and (not dst.exists() or dst.read_bytes() != src.read_bytes()):
            shutil.copy2(src, dst)
            print(f"fold: staged plugins/{src.name}")
    return staged


def validate(dist: pathlib.Path, m: dict, plain: str, full: str) -> list:
    errors = []
    validate.checked = 0   # the denominator: how many checks ran

    def need(ok, msg):
        validate.checked += 1
        if not ok:
            errors.append(msg)

    need(re.fullmatch(r"\d+\.\d+\.\d+", plain) is not None, f"plugin version {plain!r} must be plain X.Y.Z")
    need(m.get("name") == NAME, f"manifest name is {m.get('name')!r}, expected {NAME!r}")
    need(re.fullmatch(r"[A-Za-z0-9_]+", m.get("name") or "") is not None, "name may only hold letters, digits and _")
    need(m.get("version_number") == full, f"manifest version {m.get('version_number')!r} != {full!r}")
    need(len(m.get("description", "")) <= MAX_DESCRIPTION,
         f"description is {len(m.get('description', ''))} chars, over {MAX_DESCRIPTION}")
    need(bool(m.get("dependencies")), "manifest lists no dependencies")
    for name in ENTRIES[1:]:
        need((dist / name).is_file(), f"missing HexiumDistrib/{name}")
    # the PDB rule: the shipped PDB is the one built with the shipped DLL, and holds no home-folder path
    sys.path.insert(0, str(FORGE.parent.parent))
    try:
        import pdb_match
        res = pdb_match.check(str(dist / ENTRIES[-2]), str(dist / ENTRIES[-1]))
        ok = res[0] if isinstance(res, tuple) else bool(res)
        need(ok, f"plugins/BlightedHeart.pdb does not match the DLL ({res})")
    except Exception as e:
        need(False, f"pdb_match failed: {e}")
    pdb = (dist / ENTRIES[-1]).read_bytes() if (dist / ENTRIES[-1]).is_file() else b""
    need(b"/home/" not in pdb and b"rohan" not in pdb, "the PDB holds a home-folder path")
    readme = (dist / "README.md").read_text(encoding="utf-8") if (dist / "README.md").is_file() else ""
    need(readme.startswith("<!-- README schema v3 -->"), "README line 1 must be the schema v3 marker (forge it)")
    need("](#" not in readme and '<a href="#' not in readme, "README has jump links (stores break them)")
    need(re.search(r"!\[[^\]]*\]\((?!https://)", readme) is None, "README has an image without an https:// address")
    need(f"VERSION-{full.replace('-', '--')}-" in readme, f"README VERSION badge does not say {full}")
    need(f"NEW_IN_{full.replace('-', '--')}" in readme, f"README has no NEW IN {full} banner")
    icon = (dist / "icon.png").read_bytes() if (dist / "icon.png").is_file() else b""
    need(icon[:8] == b"\x89PNG\r\n\x1a\n" and icon[16:24] == (256).to_bytes(4, "big") * 2,
         "icon.png must be a 256x256 PNG")
    return errors


def pack(dist: pathlib.Path, out: pathlib.Path) -> None:
    tmp = out.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for entry in ENTRIES:
            assert "\\" not in entry
            info = zipfile.ZipInfo(entry, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (dist / entry).read_bytes())
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None, "zip integrity check failed"
        assert z.namelist() == ENTRIES, f"unexpected entries: {z.namelist()}"
    tmp.replace(out)
    digest = hashlib.sha256((dist / ENTRIES[-2]).read_bytes()).hexdigest()
    print(f"fold: {out.name}  ({out.stat().st_size:,} bytes, dll sha256 {digest[:16]}...)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="plain X.Y.Z (the plugin version)")
    ap.add_argument("--prerelease", default="", help="alpha.N / beta.N / rc.N, or empty for a release")
    ap.add_argument("--dist", required=True, type=pathlib.Path)
    ap.add_argument("--dll", required=True, type=pathlib.Path)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    dist, dll = a.dist.resolve(), a.dll.resolve()
    if not dll.exists():
        print(f"fold: no built DLL at {dll}", file=sys.stderr)
        return 1
    if a.prerelease and not PRE_RELEASE.fullmatch(a.prerelease):
        print(f"fold: prerelease {a.prerelease!r} must be alpha.N / beta.N / rc.N", file=sys.stderr)
        return 1

    full = f"{a.version}-{a.prerelease}" if a.prerelease else a.version
    m = stamp_manifest(dist / "manifest.json", full)
    stage_licence(dist)
    stage_dll(dll, dist)

    if not forge_readme(dist):
        print("fold: NOT packing - the README did not forge")
        return 0
    errors = validate(dist, m, a.version, full)
    print(f"fold: store rules: {len(errors)} failed of {validate.checked} checks")
    if errors:
        print("fold: NOT packing - fix these first:")
        for e in errors:
            print("  -", e)
        return 0   # never fail the build over packaging; the message is the signal

    release = not a.prerelease
    out = dist / (f"{NAME}-v{full}.zip" if release else f"{NAME}-v{full}-hexium.zip")
    if release and out.exists() and not a.force:
        print(f"fold: {out.name} exists and is FROZEN (uploaded versions never change) - bump the version, or --force")
        return 0
    pack(dist, out)
    print("fold: RELEASE - upload this same zip to Hexium AND Thunderstore" if release
          else "fold: PRE-RELEASE - Hexium only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
