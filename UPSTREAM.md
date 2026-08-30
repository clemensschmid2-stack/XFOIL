# Upstream provenance

## Release

- Project: XFOIL
- Authors: Mark Drela and Harold Youngren
- Version: 6.996
- Official project page: <https://web.mit.edu/drela/Public/web/xfoil/>
- Official archive: <https://web.mit.edu/drela/Public/web/xfoil/xfoil6.996.tgz>
- Upstream publication date: 2026-01-01
- Retrieved: 2026-08-30
- HTTP `Last-Modified`: `Thu, 01 Jan 2026 15:09:01 GMT`
- HTTP `ETag`: `"a44ee-64754f905dd40"`
- Archive size: `673006` bytes
- SHA-256: `0feb71b58070d8514d830fcb0b609a10a11399d362493d7b9bbfb7343dff3f23`

## Import procedure

The archive's top-level `Xfoil/` directory was stripped so its contents form the repository root.

The source import deliberately excludes only archive metadata created by macOS:

- AppleDouble files named `._*`
- `.DS_Store` files

The 6.996 archive contained 89 such metadata files. No XFOIL source, build file, documentation, or example data was otherwise changed for the `xfoil-6.996` source import.

The upstream `README` mentions an `orrs/` directory containing an Orr--Sommerfeld database. That directory is not present in the official 6.996 archive and was therefore not added here.

## Repository history

- Commit `Import upstream XFOIL 6.996`: extracted upstream source with only the macOS metadata filtering described above.
- Tag `xfoil-6.996`: identifies that source import.
- The following commit adds GitHub-facing documentation, the GPL text, and conservative build-artifact ignores; it does not change XFOIL behavior.

Future downstream behavior changes should be kept in later commits and documented separately so comparisons with `xfoil-6.996` remain straightforward.

## Licenses

XFOIL core source headers specify GNU GPL version 2 or, at the recipient's option, any later version (`GPL-2.0-or-later`). The official project page also states that redistributions must follow the GPL.

The bundled plotting library includes `plotlib/GPL-library`, the GNU Library GPL version 2 or later (`LGPL-2.0-or-later`).
