"""Build script for Ditado.

Creates a standalone .exe via PyInstaller and optionally
packages it into a Windows installer via Inno Setup.

Usage:
    python build.py            # PyInstaller only
    python build.py --installer # PyInstaller + Inno Setup
    python build.py --clean     # Remove previous build artifacts
"""

import argparse
import os
import shutil
import subprocess
import sys


def clean():
    dirs = ["build", "dist"]
    files = ["ditado.spec"]
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Removed {d}/")
    for f in files:
        if os.path.exists(f):
            os.remove(f)
            print(f"Removed {f}")


def build_pyinstaller():
    print("=== PyInstaller ===")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "ditado.spec"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print("[OK] ditado.exe built at dist/ditado.exe")


def build_installer():
    iscc = shutil.which("iscc")
    if not iscc:
        print(
            "Inno Setup Compiler (iscc.exe) not found.\n"
            "Download it from https://jrsoftware.org/isinfo.php\n"
            "and ensure iscc.exe is in your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=== Inno Setup ===")
    result = subprocess.run(
        [iscc, os.path.join("installer", "installer.iss")],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print("[OK] Installer built at dist/")


def main():
    parser = argparse.ArgumentParser(description="Build Ditado")
    parser.add_argument("--installer", action="store_true", help="Also build Inno Setup installer")
    parser.add_argument("--clean", action="store_true", help="Remove build artifacts")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    build_pyinstaller()
    if args.installer:
        build_installer()


if __name__ == "__main__":
    main()
