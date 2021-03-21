const fs = require('fs');

const DB_PATH = './resources/unknown/defs/db.JSON';
const MAGIC_BYTES = './resources/unknown/magic.bytes.json';
const MAGIC_LEN = 4;
const OUT_FILE = './resources/unknown/magic.types.json';

const db = JSON.parse(fs.readFileSync(DB_PATH));
const bytes = JSON.parse(fs.readFileSync(MAGIC_BYTES));

function lookup(magic) {
  const magics = Object.keys(db);
  const found = new Set();
  magics.forEach((m) => {
    let lhs = m;
    let rhs = magic;
    if (m.length < MAGIC_LEN) {
      rhs = rhs.substr(0, m.length);
    } else if (m.length > MAGIC_LEN) {
      lhs = lhs.substr(0, MAGIC_LEN);
    }
    if (lhs === rhs) db[m].forEach((d) => found.add(d));
  });
  return [...found];
}

const determined = { $unknown: [] };
Object.entries(bytes).forEach(([b, c]) => {
  const matches = lookup(b);
  if (matches.length) {
    matches.forEach((m) => {
      determined[m] = (determined[m] || 0) + c;
    });
  } else {
    // eslint-disable-next-line no-underscore-dangle
    determined.$unknown.push(b);
  }
});
fs.writeFileSync(OUT_FILE, JSON.stringify(determined, null, 2));
