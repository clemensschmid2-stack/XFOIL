# XFOIL

This is an **unofficial VDS-maintained downstream** of XFOIL by Mark Drela and Harold Youngren.

The repository starts from the XFOIL 6.996 source archive published by MIT. The annotated tag `xfoil-6.996` identifies that upstream source import; repository metadata was added in the following commit. See [UPSTREAM.md](UPSTREAM.md) for the exact archive URL, checksum, extraction procedure, and the files excluded from the import.

The authoritative XFOIL project page is:

<https://web.mit.edu/drela/Public/web/xfoil/>

## Source layout

- `src/`: XFOIL and companion program sources
- `plotlib/`: bundled plotting library
- `bin/`: upstream build makefiles
- `runs/`, `cav/`: example inputs and data
- `xfoil_doc.txt`: upstream user guide
- `README`: upstream build and source notes

## Licensing

The XFOIL core source is distributed under the GNU General Public License, version 2 or later. See [COPYING](COPYING).

The bundled `plotlib` has its own GNU Library General Public License, version 2 or later; see [plotlib/GPL-library](plotlib/GPL-library).

Original copyright and license notices remain in the source files.
