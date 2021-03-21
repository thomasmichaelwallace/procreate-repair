/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const parser = require('xml2json');

const DEFS_ROOT = './resources/unknown/defs';
const DEFS_OUT = `${DEFS_ROOT}/db.json`;

const PARSER_OPTIONS = {
  object: true,
  coerce: false,
  sanitize: true,
  trim: true,
  arrayNotation: true,
  alternateTextNode: false,
};

const magic = { /* [up-to first four bytes]: names[] */ };

const dirs = fs.readdirSync(DEFS_ROOT).filter((f) => !f.includes('.'));
dirs.forEach((d) => {
  const files = fs.readdirSync(path.join(DEFS_ROOT, d)).map((f) => path.join(DEFS_ROOT, d, f));
  files.forEach((f) => {
    const data = fs.readFileSync(f);
    const { TrID: [xml] } = parser.toJson(data, PARSER_OPTIONS);

    if (xml.Info.length > 1) throw new TypeError(`Too many Info nodes ${f}`);
    const { Info: [{ FileType: [fileType], Ext: extensions }] } = xml;

    let description = fileType;
    if (extensions) {
      if (extensions.length > 1) throw new TypeError(`Too many Ext nodes: ${f}`);
      if (typeof extensions[0] === 'string') {
        description = `${description} (${extensions[0]})`;
      }
    }

    const { FrontBlock: [{ Pattern: patterns }] } = xml;
    const bytes = patterns.map((p) => p.Bytes[0]);

    bytes.forEach((b) => {
      magic[b] = magic[b] || [];
      magic[b].push(description);
    });

    console.log(`added ${description}: ${bytes}`);
  });
});

fs.writeFileSync(DEFS_OUT, JSON.stringify(magic, null, 2));
