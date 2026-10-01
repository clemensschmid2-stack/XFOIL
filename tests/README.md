# XFOIL validation

The build script, parity harness, harness unit tests, and fixed official 6.996
Windows reference belong to this repository. They run without a VDS checkout.
The reference executable, DLLs, source archive, notices, and manifest were moved
byte-for-byte from VDS; their provenance and hashes are unchanged.

From this repository root:

```powershell
python -m pytest -q tests
python scripts/verify_xfoil_parity.py --output build/parity-new
```

The numerical gate requires Windows and MinGW GCC/GFortran (default
`C:/msys64/mingw64/bin`, override with `--compiler`). It builds candidates in the
new output directory. It never builds, downloads, replaces, or installs the
reference. All eight official-capacity comparisons and eight enlarged-capacity
cases execute both normal and bounds-checked candidates; convergence, malformed
outputs, missing angles, bounds errors, blocked execution and numerical
mismatches remain failures. Refinement tolerances are unchanged.

`--builds <previous-report-directory>` can reuse candidate binaries only when
source, compiler and binary hashes match. It still reruns every comparison.
Reference hashes and inventory are verified on every run. Output directories
must be fresh. Candidate builds never modify the installed runtime.

The repository's validation workflow runs harness regressions when XFOIL code,
build scripts, tests, or references change. The complete numerical comparison
is also required locally before affected merges; a green harness-only job is
not numerical sign-off. VDS runs these checks only for an XFOIL revision/build/
reference change or an explicit full-release request, not for simulator edits.
