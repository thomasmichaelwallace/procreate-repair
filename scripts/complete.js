/* eslint-disable no-console */
const fs = require('fs');

const PARTIALS_FILE = './resources/recovered/partials.fragments.json';
const WRITE_PARTIALS = false;
const WRITE_IMPLIED = false;
const WRITE_LAYERS = false;

const everything = JSON.parse(fs.readFileSync(PARTIALS_FILE));
console.log('successfully read', everything.length, 'fragments');

// assume contiguous blocks should remain together
// augment with block prior to partials filter for consistency
everything.forEach((p, i) => {
  if (p.valid) return;
  /* eslint-disable no-param-reassign */
  p.files.forEach((f) => { f.block = i; });
  p.dirs.forEach((d) => { d.block = i; });
  /* eslint-enable no-param-reassign */
});

// ignore embedded, but otherwise complete, zip fragments
const partials = everything.filter((e) => e.valid !== true);
console.log('found ', partials.length, ' partials');

function isUuid(str) {
  // files including uuids are chunks (compressed bitmap tiles)
  const uuid = /\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b/i;
  return !!str.match(uuid);
}
function parseUid(str) {
  const no = str.split(/[()]/)[1];
  return Number.parseInt(no, 10);
}
const archives = {};
const chunks = {};
const layers = {};
const corruptLayers = {};
const alternatives = {};
partials.forEach((p) => {
  p.files.forEach((f) => {
    if (f.name === 'Document.archive') {
      // each drawing includes a descriptive document.archive
      if (archives[f.fid]) console.warn(' > duplicate archive fid', f.fid);
      const filename = `./resources/recovered/archives/${f.fid.replace(/[[\] ,/]/g, '_')}.json.plist.json`;
      const data = JSON.parse(fs.readFileSync(filename));
      const refs = data.$objects.filter((s) => typeof s === 'string' && isUuid(s));
      const compositeRef = parseUid(data.$objects[1].composite);
      const uuidRef = parseUid(data.$objects[compositeRef].UUID);
      /* eslint-disable no-param-reassign */
      f.composite = data.$objects[uuidRef];
      f.refs = refs;
      /* eslint-enable no-param-reassign */
      archives[f.fid] = f;
    } else if (isUuid(f.name)) {
      if (chunks[f.fid]) {
        const existing = chunks[f.fid];

        // note alternatives for better block resolution
        alternatives[f.fid] = alternatives[f.fid] || [existing];
        alternatives[f.fid].push(f);

        // attempt to resolve most complete alternatives
        if (f.corrupt > 0) {
          if (existing.corrupt > 0) {
            console.warn(' > could not replace corrupt duplicate', f.fid, 'block kept', existing.block, '/', f.block);
          }
          // do not replace existing whole file with corrupt version
        } else if (chunks[f.fid].corrupt > 0) {
          // prefer non-corrupt version
          chunks[f.fid] = existing;
        } else {
          const thatSize = existing.end - existing.start;
          const thisSize = f.end - f.start;
          if (thisSize !== thatSize) {
            console.warn(' > inconsistent duplicates discovered:', f.block, thisSize, '/', existing.block, thatSize);
          }
        }
      }
      chunks[f.fid] = f;
      // all chunks in a layer are written at the same ts
      const [uuid, _, ts] = f.fid.split('/'); // eslint-disable-line no-unused-vars
      const layerId = `${uuid}/${ts}`;
      layers[layerId] = layers[layerId] || [];
      layers[layerId].push(f.fid);
      corruptLayers[layerId] = corruptLayers[layerId] || [];
      if (chunks[f.fid].corrupt > 0) corruptLayers[layerId].push(f.fid);
    }
  });
});
console.log('archives:', Object.keys(archives).length);
console.log(' (corrupt):', Object.values(archives).filter((f) => f.corrupt > 0).length);
console.log('chunks:', Object.keys(chunks).length);
console.log(' (corrupt):', Object.values(chunks).filter((f) => f.corrupt > 0).length);
console.log(' (alternatives):', Object.keys(alternatives).length);
console.log('layers', Object.keys(layers).length);

// attempt to recover using central zip directory
partials.forEach((p) => {
  if (p.dirs.length === 0) return;
  console.log('considering block', p.dirs[0].block);

  const block = {
    bid: p.dirs[0].block,
    trusted: false,
    archive: null,
    found: [],
    missing: [],
    corrupt: [],
    layers: new Set(),
  };

  // we can trust the cdr if the zip end block was found and it is prefixed by files
  block.trusted = !!(p.files.length > 0 && p.end > 0);

  console.log(' > cdr trusted:', block.trusted);
  if (block.trusted) return; // skip for now

  p.dirs.forEach((d) => {
    // only chunks and the archive are important
    if (d.name !== 'Document.archive' && !isUuid(d.name)) return;

    if (isUuid(d.ref)) {
      const [uuid, _, ts] = d.ref.split('/'); // eslint-disable-line no-unused-vars
      const layerId = `${uuid}/${ts}`;
      block.layers.add(layerId);
    }

    const file = chunks[d.ref] || archives[d.ref];
    if (!file) {
      block.missing.push(d.ref);
    } else if (file.name === 'Document.archive') {
      // no archives are corrupt
      block.archive = file;
      file.used = true;
    } else if (file.corrupt > 0) {
      block.corrupt.push(file);
    } else {
      block.found.push(file);
    }
  });
  console.log(' > archive:', !!block.archive);
  console.log(' > found', block.found.length);
  console.log(' > missing', block.missing.length);
  console.log(' > corrupt', block.corrupt.length);

  if (block.trusted && block.archive) {
    console.log('writing known block ', block.bid);
    const ranges = [block.archive, ...block.found].map((f) => ({
      start: f.start, end: f.end, file: f.name,
    }));
    if (WRITE_PARTIALS) {
      fs.writeFileSync(`./resources/recovered/partials/block.${block.bid}.json`, JSON.stringify(ranges, null, 2));
    }
  }

  // // untrusted files are all but empty
  // const files = new Set([...block.found, ...block.corrupt, ...block.missing]);
  // block.layers.forEach((l) => {
  //     if (layers[l]) {
  //         layers[l].forEach((f) => {
  //             if (files.has(f)) return;
  //             console.log('     suggesting layer', f);
  //         });
  //     } else {
  //         console.log('     unknown layer referenced', l);
  //     }
  // });
});

console.log('\n== recovering ==');

const layerBlocks = {};
const refLayers = {};
Object.entries(layers).forEach(([l, v]) => {
  const [uuid, ts] = l.split('/');
  refLayers[uuid] = refLayers[uuid] || [];
  refLayers[uuid].push(ts);

  layerBlocks[uuid] = layerBlocks[uuid] || new Set();
  v.forEach((fid) => {
    const { block } = chunks[fid];
    layerBlocks[uuid].add(block);
  });
});
console.log('raw layers:', Object.keys(refLayers).length);

function getTs(ts) {
  const [lmDate, lmTime] = ts.split(',').map((n) => Number.parseInt(n.substr(1), 10));
  const datetime = lmDate * 24 * 60 * 60 + lmTime * 2;
  return datetime;
}

function findLaterWhole(layerRef) {
  const layerIds = Object.keys(layers);
  const matching = layerIds
    .filter((l) => l.startsWith(layerRef))
    .map((l) => {
      const [uuid, ts] = l.split('/');
      const corrupt = (corruptLayers[l] || []).length;
      return [l, uuid, getTs(ts), layers[l].length, corrupt];
    })
    .sort((a, b) => a[2] - b[2]);
    // console.log(matching);
  return matching.pop()[0];
}

const orphanArchives = Object.values(archives).filter((a) => !a.used);
console.log('orphan archives', orphanArchives.length);
orphanArchives.forEach((o) => {
  console.log('considering block', o.block);
  // none have unique composites
  let ambiguousCount = 0;
  /* eslint-disable no-param-reassign */
  o.layers = [];
  o.refs.forEach((r) => {
    const refs = refLayers[r];
    if (refs) {
      let layerId = `${r}/${refs[0]}`;
      if (refs.length > 1) {
        layerId = findLaterWhole(r);
        console.log(' > ambiguous layer ref', r, refs.length, '->', layerId);
        ambiguousCount += 1;
      }
      o.layers.push(layerId);
    } else {
      // no layers are lost
      console.warn(' > lost layer', r);
    }
  });

  o.chunks = new Set();
  o.layers.forEach((l) => {
    const fids = layers[l];
    if (!fids) return;
    fids.forEach((f) => {
      const file = chunks[f];
      if (file.corrupt > 0) return;
      o.chunks.add(file);
    });
  });
  /* eslint-disable no-param-reassign */
  console.log('writing block ', o.block);
  const ranges = [o, ...o.chunks].map((f) => ({
    start: f.start, end: f.end, file: f.name,
  }));
  if (WRITE_IMPLIED) {
    fs.writeFileSync(`./resources/recovered/implied/block.${o.block}.json`, JSON.stringify(ranges, null, 2));
  }

  console.log('recovery rate:', o.refs.length - ambiguousCount, '/', o.refs.length);
});

const manifest = [];
Object.entries(layers).forEach(([layerId, fids]) => {
  const ranges = fids
    .map((f) => chunks[f])
    .filter((f) => f && f.corrupt < 0)
    .map((f) => ({ start: f.start, end: f.end, name: f.name }));

  if (ranges.length === 0) {
    console.log(' > empty layer', layerId);
    return;
  }

  const filename = `${layerId.replace(/(\/\[|, |\])/g, '_')}.json`;
  const fullPath = `./resources/recovered/layers/json/${filename}`;
  fs.writeFileSync(fullPath, JSON.stringify(ranges, null, 2));
  manifest.push(fullPath);
});
if (WRITE_LAYERS) {
  fs.writeFileSync('./resources/recovered/layers/manifest.json', JSON.stringify(manifest, null, 2));
}
