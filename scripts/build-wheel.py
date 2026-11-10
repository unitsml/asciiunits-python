"""Build one host-platform wheel from the pinned Rust source checkout."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--rust-source", required=True, type=Path)
    cli.add_argument("--target-dir", required=True, type=Path)
    cli.add_argument("--wheel-dir", required=True, type=Path)
    cli.add_argument("--cargo", default="cargo")
    cli.add_argument("--offline", action="store_true")
    args = cli.parse_args()
    source = args.rust_source.resolve()
    pins = json.loads((ROOT / "native-source.json").read_bytes())
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if revision != pins["native_source_commit"]:
        raise RuntimeError("Rust checkout is at a different revision")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=source):
        raise RuntimeError("Rust checkout must be clean")
    if digest(source / "artifacts" / "unitsml.json") != pins["artifact_sha256"]:
        raise RuntimeError("Artifact differs from the pinned bytes")
    env = os.environ.copy()
    target = args.target_dir.resolve()
    env["CARGO_TARGET_DIR"] = str(target)
    locked = ["--locked", *(["--offline"] if args.offline else [])]
    subprocess.run([args.cargo, "build", *locked, "--jobs", "2"], cwd=source, env=env, check=True)
    name = "asciiunits.dll" if sys.platform == "win32" else (
        "libasciiunits.dylib" if sys.platform == "darwin" else "libasciiunits.so"
    )
    binary = target / "debug" / name
    rustc = env.get("RUSTC", "rustc")
    version = subprocess.check_output([rustc, "-vV"], text=True)
    host = next(line.removeprefix("host: ") for line in version.splitlines() if line.startswith("host: "))
    metadata = json.loads(subprocess.check_output(
        [args.cargo, "metadata", *locked, "--format-version", "1", "--filter-platform", host],
        cwd=source, env=env,
    ))
    with TemporaryDirectory(prefix="asciiunits-wheel-") as temporary:
        staging = Path(temporary)
        notices = staging / "licenses"
        notices.mkdir()
        dependencies = []
        for package in metadata["packages"]:
            base = Path(package["manifest_path"]).parent
            name_version = f"{package['name']}-{package['version']}"
            files = {path for path in base.iterdir() if path.is_file() and
                     path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))}
            if package.get("license_file"):
                files.add(base / package["license_file"])
            if package["name"] == "parsanol":
                if not package["source"].endswith("#" + pins["parsanol"]):
                    raise RuntimeError("Cargo resolved a different Parsanol source")
                # The locked Parsanol crate is nested in its Git workspace.
                files.update(path for path in base.parent.iterdir() if path.is_file()
                             and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")))
                if not files:
                    raise RuntimeError("Parsanol's upstream license is missing")
            recorded = {}
            for path in sorted(files):
                destination = notices / name_version / path.name
                destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(path, destination)
                recorded[str(destination.relative_to(notices))] = digest(destination)
            dependencies.append({
                "name": package["name"], "version": package["version"],
                "license": package.get("license"), "notices": recorded,
            })
        (notices / "manifest.json").write_text(json.dumps(dependencies, indent=2) + "\n")
        receipt = staging / "build-info.json"
        receipt.write_text(json.dumps({
            **pins, "library": binary.name, "sha256": digest(binary), "abi_version": 1,
            "cargo_lock_sha256": digest(source / "Cargo.lock"), "rustc": version.splitlines()[0],
            "target": host, "profile": "dev-debug0",
            "platform_tag": sysconfig.get_platform().replace("-", "_").replace(".", "_"),
        }, indent=2) + "\n")
        env["ASCIIUNITS_NATIVE"] = str(binary)
        env["ASCIIUNITS_NATIVE_RECEIPT"] = str(receipt)
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
             "--wheel-dir", str(args.wheel_dir.resolve()), "."],
            cwd=ROOT, env=env, check=True,
        )


if __name__ == "__main__":
    main()
