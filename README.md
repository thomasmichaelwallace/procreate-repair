# procreate-repair

Tools to repair Procreate files following `ChkDsk` dump of `.CHK` files.

Shared as-is, just in case someone else needs to recover a bunch of [Procreate](https://procreate.art/) files; the process is likely to be adaptable.

## Outline

See `procreate_repair/__main__.py` for usage of the python modules to:
 * detect zips (which are probably procreate files)
 * extract previews, and then complete procreate files, from intact ranges
 * extract orphaned procreate document archives descriptors
 * attempt to recover and reassemble procreate files from document archives
 * extract all layers, regardless of how in tact they are

These works in tandem with the scripts in `./scripts`:
 * `complete.js` processes the detected ranges:
    - find whole files embedded in the chunks
    - attempt to replace partial layers with whole versions repeated elsewhere
    - attempt ro rebuild zip archives
    - identify all document archives (including orphaned ones)
    - attempt to reassemble files from orphaned archives
    - identify all layers (including orphaned ones)
 * `praseMagic.js` build a database of magic byte numbers from the trid database
 * `determine.js` attempt to identify unknown blocks from their magic bytes

## Prior Art

These tools owe a lot of their smarts to the following people's work:

* [jaromvogel/ProcreateViewer](https://github.com/jaromvogel/ProcreateViewer)
* [redstrate/procreate-viewer](https://github.com/redstrate/procreate-viewer)
* [TrID file type / file extension definitions](https://mark0.net/soft-trid-deflist.html)
* [PKZip specification](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)