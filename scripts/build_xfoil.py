"""Build the pinned XFOIL source for Windows without modifying the submodule."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT
DEFAULT_BUILD = DEFAULT_SOURCE / "build-windows"

PLOT_FORTRAN = (
    "plt_base.f", "plt_font.f", "plt_util.f", "plt_color.f",
    "set_subs.f", "gw_subs.f", "ps_subs.f", "pdf_subs.f",
    "plt_old.f", "plt_3D.f",
)
XFOIL_FORTRAN = (
    "xfoil.f", "xpanel.f", "xoper.f", "xtcam.f", "xgdes.f", "xqdes.f",
    "xmdes.f", "xsolve.f", "xbl.f", "xblsys.f", "xpol.f", "xplots.f",
    "pntops.f", "xgeom.f", "xutils.f", "modify.f", "blplot.f", "polplt.f",
    "aread.f", "naca.f", "spline.f", "plutil.f", "iopol.f", "gui.f",
    "sort.f", "dplot.f", "profil.f", "userio.f", "frplot.f", "ntcalc.f",
)


def _tool(name: str, configured: str | None) -> str:
    candidate = configured or shutil.which(name)
    if not candidate:
        raise FileNotFoundError(
            f"Could not find {name}. Install a 64-bit MinGW toolchain or pass --{name}."
        )
    return str(Path(candidate).resolve())


def _run(command: list[str], *, cwd: Path) -> None:
    print(" ".join(command), flush=True)
    # Explicit compiler paths must also work without MinGW on the parent PATH:
    # compiler subprocesses need the matching runtime DLLs from its bin folder.
    environment = dict(os.environ)
    environment["PATH"] = str(Path(command[0]).parent) + os.pathsep + environment.get("PATH", "")
    subprocess.run(command, cwd=cwd, check=True, env=environment)


def _compile_fortran(
    compiler: str, source: Path, output: Path, include_dirs: tuple[Path, ...] = (),
    bounds_check: bool = False,
) -> None:
    command = [
        compiler, "-c", "-O2", "-fdefault-real-8", "-fallow-argument-mismatch",
        "-ffixed-line-length-none",
    ]
    if bounds_check:
        command.extend(["-fcheck=all", "-fbacktrace"])
    command.extend(f"-I{directory}" for directory in include_dirs)
    command.extend([str(source), "-o", str(output)])
    _run(command, cwd=source.parent)


def build(source: Path, build_dir: Path, gfortran: str | None, gcc: str | None,
          bounds_check: bool = False) -> Path:
    source = source.resolve()
    build_dir = build_dir.resolve()
    if not (source / "src" / "xfoil.f").is_file():
        raise FileNotFoundError(f"XFOIL source is incomplete: {source}")
    fc = _tool("gfortran", gfortran)
    cc = _tool("gcc", gcc)
    object_dir = build_dir / "obj"
    install_dir = build_dir / "install"
    object_dir.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    objects: list[Path] = []
    plot = source / "plotlib"
    for name in PLOT_FORTRAN:
        src = plot / name
        obj = object_dir / f"plot_{src.stem}.o"
        _compile_fortran(fc, src, obj, (plot,), bounds_check)
        objects.append(obj)
    pdf_stub = plot / "pdf" / "hpdf-stubs.f"
    pdf_obj = object_dir / "plot_hpdf-stubs.o"
    _compile_fortran(fc, pdf_stub, pdf_obj, (plot,), bounds_check)
    objects.append(pdf_obj)

    win_source = plot / "win32" / "W32pthread.c"
    win_obj = object_dir / "plot_W32pthread.o"
    _run([
        cc, "-c", "-O2", "-DUNDERSCORE", "-DDBL_ARGS",
        f"-I{plot}", f"-I{plot / 'win32'}", str(win_source), "-o", str(win_obj),
    ], cwd=win_source.parent)
    objects.append(win_obj)

    src_dir = source / "src"
    for name in XFOIL_FORTRAN:
        src = src_dir / name
        obj = object_dir / f"xfoil_{src.stem}.o"
        _compile_fortran(fc, src, obj, (src_dir, plot), bounds_check)
        objects.append(obj)
    osmap = source / "osrc" / "osmap.f"
    osmap_obj = object_dir / "xfoil_osmap.o"
    _compile_fortran(fc, osmap, osmap_obj, (source / "osrc", src_dir), bounds_check)
    objects.append(osmap_obj)
    getosfile = source / "osrc" / "getosfile.c"
    getosfile_obj = object_dir / "xfoil_getosfile.o"
    _run([cc, "-c", "-O2", "-DUNDERSCORE", str(getosfile), "-o", str(getosfile_obj)], cwd=getosfile.parent)
    objects.append(getosfile_obj)

    executable = install_dir / "xfoil.exe"
    _run([
        fc, "-O2", "-fdefault-real-8", "-o", str(executable),
        *(str(item) for item in objects),
        "-luser32", "-lgdi32", "-lpthread",
    ], cwd=build_dir)

    compiler_bin = Path(fc).parent
    for dll_name in ("libgcc_s_seh-1.dll", "libgfortran-5.dll", "libquadmath-0.dll", "libwinpthread-1.dll"):
        dll = compiler_bin / dll_name
        if dll.is_file():
            shutil.copy2(dll, install_dir / dll.name)
    if not executable.is_file():
        raise RuntimeError("XFOIL link completed without producing xfoil.exe")
    print(f"Built XFOIL: {executable}")
    return executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--gfortran")
    parser.add_argument("--gcc")
    parser.add_argument("--bounds-check", action="store_true")
    args = parser.parse_args()
    try:
        build(args.source, args.build_dir, args.gfortran, args.gcc, args.bounds_check)
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"XFOIL build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
