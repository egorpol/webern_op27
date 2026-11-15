// Webern Op. 27 viewer: the MEI rendered by Verovio with the encoded page and
// system breaks, the editorial notes, and the scan: the page images of
// webern_op27-facsimile, once the visitor confirms that the print is in the
// public domain where they are, or their own copy of the IMSLP PDF. Zones come
// from the MEI. Playback runs Verovio's MIDI through player.js, off by default.

const VEROVIO_URL = 'https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js';
const VEROVIO_SRI = 'sha384-7oICD/hf52uWdE8X0lMFqe7iIspaUj3aQjeZUnBQZpxjrZcHtqlRd3C78cje2e19';
// pdf.js 6 decodes this scan's fax-encoded images with wasm/jbig2.wasm, which
// cdnjs does not carry; jsDelivr serves the whole npm package.
const PDFJS_URL = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/';
const REPO_BLOB = 'https://github.com/egorpol/webern_op27/blob/main/';
// The page images live in their own repository: the print is still protected in the US.
const SCAN_URL = 'https://egorpol.github.io/webern_op27-facsimile/ue1937/';
const SCAN_CONFIRMED = 'webern-op27-scan-confirmed';
// The layout of camat_v2's facsimile notebook: one rendered page per printed page.
const VEROVIO_OPTIONS = {
  breaks: 'encoded', adjustPageHeight: true, footer: 'none', svgViewBox: true, condense: 'none',
  scale: 35, spacingLinear: 0.25, spacingNonLinear: 0.6, minLastJustification: 0,
};
const XML_NS = 'http://www.w3.org/XML/1998/namespace';
const SVG_NS = 'http://www.w3.org/2000/svg';
const STORE = { db: 'webern-op27-viewer', store: 'files', key: 'imslp-pdf' };
const SETTINGS = { playback: 'webern-op27-playback', markNotes: 'webern-op27-mark-notes', measureBoxes: 'webern-op27-measure-boxes' };
const PLAYBACK_SETTINGS = { tempo: 'webern-op27-tempo', repeats: 'webern-op27-repeats' };
const SOUNDFONT_ROOT = 'https://cdn.jsdelivr.net/gh/gleitz/midi-js-soundfonts@044fab8e1456bfafc5776e86dfd6bb8697149aef/FluidR3_GM/';
const SAMPLE_FILES = {
  0: { url: `${SOUNDFONT_ROOT}acoustic_grand_piano-mp3.js`, integrity: 'sha384-Oe49rvfDnHMSSNlo8V6a4XyotASwNvpbHFgo0IOcyk8OFIXv8byikUYK2I3ONEfa' },
};
// Verovio writes both staves to channel 0 without a program change: GM 0, the piano.
const PARTS = [{ channel: 0, program: 0 }];
const MM_UNITS = { 2: 'half', 4: 'quarter', 8: 'eighth' };
// Target sounding length for each unaccented grace note in MIDI playback.
const GRACE_MS = 70;

const $ = (id) => document.getElementById(id);
const xmlId = (el) => el.getAttributeNS(XML_NS, 'id');
const refs = (value) => (value || '').split(/\s+/).filter(Boolean).map((v) => v.replace(/^#/, ''));
const STATUS_HINT = $('status').textContent;

const state = { mvt: null, model: null, page: 1, pinned: null, annot: null };
const settings = { playback: false, markNotes: false, measureBoxes: false };
const playback = {
  engine: null, ready: null, context: null, token: 0, state: 'idle', loadingMovement: true,
  percent: 100, repeats: true, engineModel: null, renders: 0, q: 0, start: null, pinAtPlay: null,
  follow: false, active: new Set(), event: 0, measure: null,
};
const models = new Map();
const pagesReady = fetch('facsimiles/ue1937/pages.json').then((r) => {
  if (!r.ok) throw new Error(`facsimiles/ue1937/pages.json: HTTP ${r.status}`);
  return r.json();
});
let toolkit = null;
let pdf = null;
let scanImages = null; // file → Promise<ImageBitmap>, while the hosted scan is shown
let mvtToken = 0;
let facsToken = 0;
let renderTask = null;

// ---------------------------------------------------------------- loading

function loadVerovio() {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = VEROVIO_URL;
    script.integrity = VEROVIO_SRI;
    script.crossOrigin = 'anonymous';
    // The load event fires right after the script ran, before the wasm is ready.
    script.onload = () => { verovio.module.onRuntimeInitialized = () => resolve(new verovio.toolkit()); };
    script.onerror = () => reject(new Error('Verovio could not be loaded from jsDelivr.'));
    document.head.append(script);
  });
}

function getModel(key) {
  if (!models.has(key)) {
    const file = `mei/webern-op27-${key}.mei`;
    models.set(key, Promise.all([fetch(file), pagesReady]).then(async ([response, pages]) => {
      if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
      return readModel(key, await response.text(), pages);
    }));
  }
  return models.get(key);
}

function enclosingMeasure(el) {
  for (let node = el; node; node = node.parentElement) {
    if (node.localName === 'measure') return xmlId(node);
  }
  return null;
}

function readModel(key, text, pages) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length) throw new Error(`Movement ${key}: the MEI is not well-formed.`);
  const model = {
    key, text, ids: new Map(), measures: new Map(), byN: new Map(), pages: [],
    surfaces: new Map(), zones: new Map(), annots: [], noted: new Set(), svg: new Map(), pageCount: 0,
  };
  const edition = doc.querySelector('editionStmt > edition');
  model.edition = edition ? `${edition.textContent.trim()} (version ${edition.getAttribute('n')})` : '';
  // Movement II plays its printed repeats from an explicit <expansion>.
  model.hasRepeats = doc.getElementsByTagName('expansion').length > 0;
  // The printed mark, not a MIDI number: "ca" and the unit are what the print gives.
  const tempo = doc.querySelector('music tempo[mm]');
  model.tempoMark = `${tempo.hasAttribute('mm.dots') ? 'dotted ' : ''}${MM_UNITS[tempo.getAttribute('mm.unit')]} ca ${tempo.getAttribute('mm')}`;

  for (const surface of doc.getElementsByTagName('surface')) {
    const graphic = surface.getElementsByTagName('graphic')[0];
    const file = graphic.getAttribute('target').split('/').pop();
    const page = pages.pages.find((p) => p.file === file);
    model.surfaces.set(xmlId(surface), {
      file,
      sha256: page?.sha256,
      width: Number(graphic.getAttribute('width')),
      height: Number(graphic.getAttribute('height')),
      pdfPage: page?.pdf_page_number,
      printed: surface.getAttribute('n'),
    });
    for (const zone of surface.getElementsByTagName('zone')) {
      const [ulx, uly, lrx, lry] = ['ulx', 'uly', 'lrx', 'lry'].map((a) => Number(zone.getAttribute(a)));
      model.zones.set(xmlId(zone), { surface: xmlId(surface), x: ulx, y: uly, w: lrx - ulx, h: lry - uly, measure: null });
    }
  }

  const annots = [];
  for (const el of doc.getElementsByTagName('music')[0].getElementsByTagName('*')) {
    const id = xmlId(el);
    if (el.localName === 'pb') model.pages.push({ n: el.getAttribute('n'), surface: refs(el.getAttribute('facs'))[0] });
    if (el.localName === 'measure') {
      const n = el.getAttribute('n');
      const zone = refs(el.getAttribute('facs'))[0];
      model.measures.set(id, { id, n, zone, page: Math.max(model.pages.length, 1) });
      model.byN.set(n, id);
      if (model.zones.has(zone)) model.zones.get(zone).measure = id;
    }
    if (el.localName === 'annot') annots.push(el);
    if (id) model.ids.set(id, { name: el.localName, measure: enclosingMeasure(el) });
  }
  // Not measures.size: movement II counts its pickup as bar 0.
  model.lastBar = [...model.measures.values()].at(-1).n;
  model.annots = annots.map((el) => {
    const targets = refs(el.getAttribute('plist'));
    const bars = [...new Set([xmlId(el), ...targets].map((t) => model.ids.get(t)?.measure).filter(Boolean))]
      .map((m) => model.measures.get(m))
      .sort((a, b) => Number(a.n) - Number(b.n));
    bars.forEach((bar) => model.noted.add(bar.id));
    return { id: xmlId(el), label: el.getAttribute('label') || el.getAttribute('type'), targets, bars, paras: [...el.getElementsByTagName('p')] };
  });
  // Consecutive grace events before a main note/chord per layer; barStart if nothing sounded earlier in the layer.
  const SOUND = new Set(['note', 'chord', 'rest', 'space', 'mRest', 'mSpace', 'multiRest']);
  const idsOf = (el) => el.localName === 'chord'
    ? [...el.children].filter((c) => c.localName === 'note').map(xmlId) : [xmlId(el)];
  const grace = (el) => (el.localName === 'note' || el.localName === 'chord')
    && (el.hasAttribute('grace') || el.closest('graceGrp'));
  model.graceGroups = [];
  for (const layer of doc.getElementsByTagName('layer')) {
    const ev = [];
    (function walk(p) { for (const el of p.children) SOUND.has(el.localName) ? ev.push(el) : walk(el); })(layer);
    for (let i = 0; i < ev.length;) {
      if (!grace(ev[i])) { i++; continue; }
      const from = i;
      while (i < ev.length && grace(ev[i])) i++;
      const next = ev[i], main = next && (next.localName === 'note' || next.localName === 'chord') ? idsOf(next) : [];
      model.graceGroups.push({ graces: ev.slice(from, i).map(idsOf), main, barStart: from === 0 });
    }
  }
  return model;
}

// ---------------------------------------------------------------- score

const current = () => state.model;

function scoreMessage(text) {
  const p = document.createElement('p');
  p.className = 'message';
  p.textContent = text;
  $('score').replaceChildren(p);
}

function setStatus(text, id = '') {
  const code = document.createElement('code');
  code.textContent = id;
  $('status').replaceChildren(id ? `${text} · ` : text, code);
}

async function showMovement(key) {
  const token = ++mvtToken;
  if (state.mvt === key) {
    // Returning to the displayed movement also cancels an intervening load.
    if (playback.loadingMovement) {
      playback.loadingMovement = false;
      playerState('idle');
      showPage(state.page);
    }
    return;
  }
  stopPlayback(true);
  playback.loadingMovement = true;
  playerState('idle');
  scoreMessage(`Loading movement ${key}…`);
  const model = await getModel(key);
  if (token !== mvtToken) return;
  toolkit.loadData(model.text);
  model.pageCount = toolkit.getPageCount();
  Object.assign(state, { mvt: key, model, pinned: null, annot: null });
  playback.loadingMovement = false;
  $('repeats-label').hidden = !model.hasRepeats;
  $('player').dataset.movement = key;
  playerState('idle');
  updateTempo();
  document.querySelectorAll('.tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.mvt === key)));
  $('edition').textContent = model.edition;
  renderAnnots(model);
  showPage(1);
}

function showPage(page) {
  const model = current();
  page = Math.min(Math.max(page, 1), model.pageCount);
  if (!model.svg.has(page)) model.svg.set(page, toolkit.renderToSVG(page));
  $('score').innerHTML = model.svg.get(page);
  state.page = page;
  decorate();
  const printed = model.pages[page - 1]?.n;
  $('page-label').textContent = `${printed ? `p. ${printed}` : 'page'} (${page}/${model.pageCount})`;
  $('prev').disabled = page <= 1;
  $('next').disabled = page >= model.pageCount;
  applyHighlights();
  applyPlaying();
  renderFacsimile();
}

let nextPageJob = null;
function preRenderNextPage() {
  // One job at a time, replacing an obsolete target after another turn/Play.
  if (nextPageJob) {
    clearTimeout(nextPageJob.delay);
    if (nextPageJob.idle !== undefined) {
      if (window.cancelIdleCallback) window.cancelIdleCallback(nextPageJob.idle);
      else clearTimeout(nextPageJob.idle);
    }
  }
  const model = current(), page = state.page + 1;
  nextPageJob = null;
  if (!model || page > model.pageCount || model.svg.has(page)) return;
  const job = {};
  nextPageJob = job;
  const render = () => {
    if (nextPageJob !== job) return;
    nextPageJob = null;
    // getModel awaits while current() can still be the old model. The loading
    // guard also covers that interval: the toolkit holds just one movement's data.
    if (model === current() && !playback.loadingMovement && !model.svg.has(page)) {
      model.svg.set(page, toolkit.renderToSVG(page));
    }
  };
  // Let Tone refill its horizon for two update intervals before another block.
  // This task renders only SVG; insertion/decoration wait for the actual turn.
  job.delay = setTimeout(() => {
    job.idle = window.requestIdleCallback ? window.requestIdleCallback(render) : setTimeout(render, 0);
  }, 50);
}

function svgElement(name, attributes = {}) {
  const el = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

// A box behind every rendered bar, shown by the display settings. It covers
// the bar's staves only: Verovio draws a spanner in the bar where it starts,
// so a rit. extender or a beam across the barline would stretch the box over
// the next bars. An empty text draws nothing, but Chrome counts it as a point
// at (0, 0) in getBBox and stretches the box to the page corner; hide it first.
function decorate() {
  const model = current();
  for (const text of $('score').querySelectorAll('g.measure text')) {
    if (!text.textContent.trim()) text.setAttribute('display', 'none');
  }
  for (const g of $('score').querySelectorAll('g.measure')) {
    const staves = [...g.querySelectorAll(':scope > g.staff')].map((s) => s.getBBox());
    if (!model.measures.has(g.id) || !staves.length) continue;
    const x = Math.min(...staves.map((b) => b.x));
    const y = Math.min(...staves.map((b) => b.y));
    const width = Math.max(...staves.map((b) => b.x + b.width)) - x;
    const height = Math.max(...staves.map((b) => b.y + b.height)) - y;
    const rect = svgElement('rect', { x, y, width, height, class: 'measure-box' });
    if (model.noted.has(g.id)) rect.classList.add('has-note');
    g.prepend(rect);
  }
}

// Every rendered fragment of an element: the element itself and the
// continuations Verovio draws after a system break (class "id-<xml:id>").
function svgNodes(id) {
  return $('score').querySelectorAll(`[id="${CSS.escape(id)}"], .id-${CSS.escape(id)}`);
}

function applyHighlights() {
  const model = current();
  document.querySelectorAll('.is-pinned, .is-annot, .is-noted').forEach((n) => n.classList.remove('is-pinned', 'is-annot', 'is-noted'));
  if (!model) return;
  if (state.pinned) svgNodes(state.pinned).forEach((n) => n.classList.add('is-pinned'));
  if (settings.markNotes) model.annots.forEach((a) => a.targets.forEach((t) => svgNodes(t).forEach((n) => n.classList.add('is-noted'))));
  const annot = state.annot && model.annots.find((a) => a.id === state.annot);
  annot?.targets.forEach((t) => svgNodes(t).forEach((n) => n.classList.add('is-annot')));
  for (const rect of $('zones').children) rect.classList.toggle('is-pinned', rect.dataset.measure === state.pinned);
  document.querySelectorAll('.notes li > button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.annot === state.annot)));
}

function applySettings() {
  for (const el of [$('score'), document.querySelector('.facs-page')]) {
    el.classList.toggle('mark-notes', settings.markNotes);
    el.classList.toggle('show-boxes', settings.measureBoxes);
  }
  $('player').hidden = !settings.playback;
  applyHighlights();
}

function pin(measureId, { hash = true } = {}) {
  const model = current();
  const measure = model.measures.get(measureId);
  if (!measure) return;
  stopFollowing();
  state.pinned = measureId;
  if (hash) history.replaceState(null, '', `#${model.key}/${measure.n}`);
  if (measure.page !== state.page) showPage(measure.page);
  else applyHighlights();
  setStatus(`Movement ${model.key}, bar ${measure.n}`, measureId);
}

// Hover colours one element in the score (a note, or the bar from a zone)
// and outlines its bar's zone on the scan.
function hover(id, measureId) {
  document.querySelectorAll('.is-hover').forEach((n) => n.classList.remove('is-hover'));
  if (id) svgNodes(id).forEach((n) => n.classList.add('is-hover'));
  for (const rect of $('zones').children) rect.classList.toggle('is-hover', Boolean(measureId) && rect.dataset.measure === measureId);
}

// The nearest rendered ancestor that carries an xml:id from the MEI.
function sourceElement(target) {
  const model = current();
  for (let node = target; node && node !== $('score'); node = node.parentElement) {
    if (model.ids.has(node.id)) return node.id;
    const token = [...node.classList].find((c) => c.startsWith('id-') && model.ids.has(c.slice(3)));
    if (token) return token.slice(3);
  }
  return null;
}

function inspect(target) {
  const model = current();
  const id = model && sourceElement(target);
  if (!id) { hover(null); return; }
  const info = model.ids.get(id);
  const measure = model.measures.get(info.measure);
  hover(id, info.measure);
  setStatus(measure ? `Bar ${measure.n}, ${info.name}` : info.name, id);
}

// ---------------------------------------------------------------- playback

// The player and its samples are the same as in the DdT 1/11 edition. Verovio's MIDI
// carries the notes at one velocity and one tempo: see the note in the player.
function playerState(value) {
  playback.state = value;
  $('player').dataset.state = value;
  $('play').textContent = value === 'loading' ? 'Loading…' : value === 'playing' ? 'Pause' : 'Play';
  $('play').disabled = playback.loadingMovement || !current() || value === 'loading';
  $('stop').disabled = playback.loadingMovement || !current() || value === 'idle';
}

function stopFollowing() {
  playback.follow = false;
  $('player').dataset.follow = 'false';
}

function clearPlaying() {
  for (const root of [$('score'), $('zones')]) {
    root.querySelectorAll('.is-playing').forEach((n) => n.classList.remove('is-playing'));
  }
}

function applyPlaying() {
  clearPlaying();
  if (playback.state !== 'playing') return;
  const model = current();
  for (const raw of playback.active) {
    const id = model.playingIds.get(raw);
    if (id) svgNodes(id).forEach((n) => n.classList.add('is-playing'));
  }
  for (const rect of $('zones').children) rect.classList.toggle('is-playing', rect.dataset.measure === playback.measure);
}

function showPosition(q, measureId = playback.measure) {
  playback.q = q;
  playback.measure = measureId;
  const model = current();
  const measure = model?.measures.get(measureId);
  Object.assign($('player').dataset, { position: q, measure: measure?.n || '' });
  const text = measure ? `Bar ${measure.n} / ${model.lastBar}` : '–';
  if ($('player-position').textContent !== text) $('player-position').textContent = text;
}

function advanceCursor(q) {
  const model = current();
  if (!model?.playbackMap) return;
  let changed = false;
  while (playback.event < model.playbackMap.length && model.playbackMap[playback.event].qstamp <= q + 1 / model.midi.header.ppq + 1e-9) {
    const event = model.playbackMap[playback.event++];
    for (const id of event.off) playback.active.delete(id);
    for (const id of event.on) playback.active.add(id);
    if (event.measure) playback.measure = event.measure;
    changed = true;
  }
  showPosition(q);
  const measure = model.measures.get(playback.measure);
  if (playback.follow && measure && measure.page !== state.page) {
    showPage(measure.page);
    preRenderNextPage();
  } else if (changed) applyPlaying();
}

function resetCursor(q, measure) {
  clearPlaying();
  playback.active.clear();
  playback.event = 0;
  playback.measure = measure;
  advanceCursor(q);
}

function stopPlayback(movementSwitch = false) {
  ++playback.token; // Pending imports/sample loads may finish, but cannot start.
  const start = !movementSwitch && playback.start;
  playback.engine?.stop(start?.q || 0);
  if (movementSwitch) playback.engineModel = null;
  stopFollowing();
  playerState('idle');
  clearPlaying();
  playback.active.clear();
  if (movementSwitch) {
    playback.start = null;
    playback.pinAtPlay = null;
  }
  showPosition(start?.q || 0, start?.id || null);
  const measure = current()?.measures.get(start?.id);
  if (measure && measure.page !== state.page) showPage(measure.page);
  if (movementSwitch) setStatus(STATUS_HINT);
  else if (measure) setStatus(`Stopped at bar ${measure.n}`);
}

async function getPlayer() {
  if (!playback.ready) {
    playback.ready = import('./player.js').then(({ createPlayer }) => createPlayer({
      context: playback.context, samples: SAMPLE_FILES,
      onTempo: (tempo) => { if (playback.engineModel === current()) showTempo(tempo); },
      onPosition: advanceCursor, onEnd: () => stopPlayback(),
    })).then((engine) => { playback.engine = engine; return engine; }).catch((error) => {
      playback.ready = null;
      throw error;
    });
  }
  return playback.ready;
}

function cachePlayback(model, engine) {
  if (model.midi && model.timemap) return;
  // This toolkit still holds model.text: movement/token checked immediately before this call.
  model.midi = engine.parseMidi(toolkit.renderToMIDI());
  ++playback.renders;
  $('player').dataset.midiRenders = playback.renders;
  model.timemap = toolkit.renderToTimemap().sort((a, b) => a.qstamp - b.qstamp);
  model.playingIds = new Map();
  function notated(id) {
    if (!id) return null;
    if (model.playingIds.has(id)) return model.playingIds.get(id);
    const stripped = id.replace(/-rend\d+$/, '');
    const mapped = model.ids.has(id) ? id : model.ids.has(stripped) ? stripped : toolkit.getNotatedIdForElement(id);
    const result = model.ids.has(mapped) ? mapped : null;
    model.playingIds.set(id, result);
    return result;
  }
  model.playbackMap = model.timemap.map((event) => {
    const on = (event.on || []).filter((id) => notated(id));
    const off = (event.off || []).filter((id) => notated(id));
    return { qstamp: event.qstamp, on, off, measure: model.ids.get(notated(on[0] || ''))?.measure };
  });
  model.measureQ = new Map();
  for (const measure of model.measures.values()) {
    const ms = toolkit.getTimeForElement(measure.id);
    // Find by the measured millisecond time; never key or equate qstamp floats.
    let low = 0, high = model.timemap.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      if (model.timemap[mid].tstamp < ms) low = mid + 1;
      else high = mid;
    }
    let i = Math.min(low, model.timemap.length - 1);
    if (i > 0 && Math.abs(model.timemap[i - 1].tstamp - ms) < Math.abs(model.timemap[i].tstamp - ms)) --i;
    // Play-from-bar keeps this qstamp: do not pull it back to a lengthened bar-start grace.
    model.measureQ.set(measure.id, model.timemap[i].qstamp);
    model.playbackMap[i].measure = measure.id;
  }
  adjustGraceNotes(model, notated);
}

// Verovio plays each unaccented grace for ~27ms, ending on the main beat (or taking the beat
// when the main is first in the bar). Stretch every grace group to GRACE_MS and, in the
// bar-start case, pull the main note back onto the beat; leave measureQ where Verovio put it.
function adjustGraceNotes(model, notated) {
  const fmt = (list) => list.sort((a, b) => a.ticks - b.ticks || a.midi - b.midi)
    .map((n) => `${n.ticks}/${n.durationTicks}/${n.midi}`).join(' ');
  if (!model.graceGroups?.length) {
    model.graceReport = { graces: '', mains: '', cuts: '', skipped: 0 };
    return;
  }
  const { ppq, tempos } = model.midi.header;
  const notes = model.midi.tracks.flatMap((t) => t.notes);
  const onsets = new Map();
  for (const event of model.timemap) {
    for (const raw of event.on || []) {
      const id = notated(raw);
      if (!id) continue;
      (onsets.get(id) || onsets.set(id, []).get(id)).push(event.qstamp);
    }
  }
  const match = (id, q) => {
    const p = toolkit.getMIDIValuesForElement(id).pitch, t = q * ppq;
    const hits = notes.filter((n) => n.midi === p && Math.abs(n.ticks - t) < 1);
    return hits.length === 1 ? hits[0] : null;
  };
  const graces = [], mains = [], cuts = [];
  let skipped = 0;
  for (const group of model.graceGroups) {
    const n = group.graces.length, gIds = group.graces.flat(), count = gIds.length;
    const all = [...gIds, ...group.main], times = onsets.get(gIds[0])?.length || 0;
    if (!group.main.length || !times || all.some((id) => (onsets.get(id) || []).length !== times)) {
      skipped += count; continue;
    }
    const passes = [];
    let ok = true;
    for (let p = 0; p < times && ok; p++) {
      const gNotes = group.graces.map((ids) => ids.map((id) => match(id, onsets.get(id)[p])));
      const mNotes = group.main.map((id) => match(id, onsets.get(id)[p]));
      if (gNotes.some((ev) => ev.some((x) => !x)) || mNotes.some((x) => !x)) ok = false;
      else passes.push({ gNotes, mNotes });
    }
    if (!ok) { skipped += count; continue; }
    const edits = [];
    for (const { gNotes, mNotes } of passes) {
      const B = group.barStart ? Math.min(...gNotes[0].map((x) => x.ticks)) : Math.min(...mNotes.map((x) => x.ticks));
      const L = Math.max(1, Math.round(GRACE_MS * (tempos.filter((t) => t.ticks <= B).at(-1)?.bpm ?? 120) * ppq / 60000));
      if (B - n * L < 0) { edits.length = 0; break; }
      edits.push({ gNotes, mNotes, B, L });
    }
    if (!edits.length) { skipped += count; continue; }
    for (const { gNotes, mNotes, B, L } of edits) {
      const moved = new Set(gNotes.flat());
      for (let k = 0; k < n; k++) {
        const ticks = B - (n - k) * L;
        for (const note of gNotes[k]) {
          for (const other of notes) {
            if (moved.has(other) || other.midi !== note.midi) continue;
            if (other.ticks < ticks && other.ticks + other.durationTicks > ticks) {
              other.durationTicks = ticks - other.ticks;
              cuts.push(other);
            }
          }
          note.ticks = ticks; note.durationTicks = L; graces.push(note);
        }
      }
      if (group.barStart) {
        for (const note of mNotes) {
          note.durationTicks += note.ticks - B; note.ticks = B; mains.push(note);
        }
      }
    }
  }
  model.graceReport = { graces: fmt(graces), mains: fmt(mains), cuts: fmt(cuts), skipped };
}

const PLAYBACK_CACHE = ['midi', 'timemap', 'playingIds', 'playbackMap', 'measureQ', 'graceReport'];

// Repeats off = Verovio's expandNever: MIDI and timemap play the written order once. Verovio applies
// it at loadData, so a movement with repeats reloads; the score drawing and the page cache do not change.
function setRepeats(value) {
  playback.repeats = value;
  try { localStorage.setItem(PLAYBACK_SETTINGS.repeats, value ? '1' : '0'); } catch { /* not remembered */ }
  if (!toolkit) return;
  toolkit.setOptions({ expandNever: !value });
  $('player').dataset.repeats = String(value);
  const forget = (model) => { for (const key of PLAYBACK_CACHE) delete model[key]; };
  for (const ready of models.values()) ready.then(forget, () => {});
  const model = current();
  if (!model?.hasRepeats || playback.loadingMovement) return;
  stopPlayback();
  playback.engineModel = null;
  forget(model);
  if (!toolkit.loadData(model.text)) scoreMessage(`Verovio could not load movement ${model.key}.`);
}

function showTempo({ bpm }) {
  if ($('player').dataset.bpm !== String(bpm)) $('player').dataset.bpm = bpm;
}

function updateTempo() {
  const model = current(), bpm = model?.midi?.header.tempos[0]?.bpm;
  if (document.activeElement !== $('tempo-number')) $('tempo-number').value = playback.percent;
  $('tempo-base').textContent = model ? `100 % = ${model.tempoMark}` : '';
  if (model && playback.engineModel === model) playback.engine.setTempo(playback.percent);
  else showTempo({ bpm: bpm ? bpm * playback.percent / 100 : '' });
}

function setGlobalTempo(value) {
  playback.percent = value;
  $('tempo').value = $('tempo-number').value = value;
  updateTempo();
  try { localStorage.setItem(PLAYBACK_SETTINGS.tempo, playback.percent); } catch { /* not remembered */ }
}

async function togglePlayback() {
  if (!settings.playback || !current() || playback.loadingMovement || playback.state === 'loading') return;
  const newPin = state.pinned && state.pinned !== playback.pinAtPlay;
  if (playback.state === 'playing' && !newPin) {
    showPosition(playback.engine.pause());
    playerState('paused');
    clearPlaying();
    setStatus(`Paused at bar ${current().measures.get(playback.measure)?.n}`);
    return;
  }
  const model = current(), token = ++playback.token;
  const resume = playback.state === 'paused' && !newPin;
  // Before the first await: preserve the native user gesture on Safari as well.
  try {
    playback.context ||= new (window.AudioContext || window.webkitAudioContext)();
    const resumed = playback.context.resume();
    playback.engine?.stop();
    playerState('loading');
    clearPlaying();
    const [engine] = await Promise.all([getPlayer(), resumed]);
    if (token !== playback.token || model !== current()) return;
    cachePlayback(model, engine);
    $('player').dataset.midiNotes = model.midi.tracks.reduce((n, t) => n + t.notes.length, 0);
    const g = model.graceReport || { graces: '', mains: '', cuts: '', skipped: 0 };
    Object.assign($('player').dataset, {
      graces: g.graces, graceMains: g.mains, graceCuts: g.cuts, graceSkipped: g.skipped,
    });
    updateTempo();
    const prepared = await engine.prepare(model.midi, PARTS);
    if (token !== playback.token || model !== current()) return;
    const id = state.pinned || [...model.measures.values()].find((m) => m.page === state.page)?.id || model.measures.keys().next().value;
    const q = resume ? playback.q : model.measureQ.get(id) || 0;
    if (!resume) playback.start = { id, q };
    playback.pinAtPlay = state.pinned;
    playback.follow = true;
    $('player').dataset.follow = 'true';
    playerState('playing');
    resetCursor(q, resume ? playback.measure : id);
    playback.engineModel = model;
    engine.play(prepared, q, playback.percent);
    preRenderNextPage();
    setStatus(`Playing from bar ${model.measures.get(playback.measure)?.n}`);
  } catch (error) {
    if (token !== playback.token || model !== current()) return;
    playback.engine?.stop();
    clearPlaying();
    playerState('error');
    const reason = /[.!?]$/.test(error.message) ? error.message : `${error.message}.`;
    setStatus(`Playback could not start: ${reason} Press Play to retry.`);
  }
}

// ---------------------------------------------------------------- notes

function inlineText(node, parent) {
  for (const child of node.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) parent.append(child.textContent.replace(/\s+/g, ' '));
    else if (child.localName === 'ref' && child.getAttribute('target')) {
      const a = document.createElement('a');
      a.href = new URL(child.getAttribute('target'), `${REPO_BLOB}mei/`).href;
      inlineText(child, a);
      parent.append(a);
    } else if (child.nodeType === Node.ELEMENT_NODE) inlineText(child, parent);
  }
}

function renderAnnots(model) {
  const list = $('annots');
  list.replaceChildren();
  for (const annot of model.annots) {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.annot = annot.id;
    const first = annot.bars[0]?.n;
    const last = annot.bars.at(-1)?.n;
    const where = document.createElement('span');
    where.className = 'where';
    where.textContent = first === last ? `Bar ${first}` : `Bars ${first}–${last}`;
    const label = document.createElement('span');
    label.className = 'label';
    label.textContent = annot.label.replace(/-/g, ' ');
    button.append(where, label);
    li.append(button);
    for (const para of annot.paras) {
      const p = document.createElement('p');
      inlineText(para, p);
      li.append(p);
    }
    list.append(li);
  }
  $('notes-heading').textContent = `Editorial notes (${model.annots.length})`;
}

function selectAnnot(id) {
  const annot = current().annots.find((a) => a.id === id);
  state.annot = state.annot === id ? null : id;
  if (state.annot && annot.bars.length) pin(annot.bars[0].id);
  else applyHighlights();
}

// ---------------------------------------------------------------- facsimile

function showFacsError(text) {
  $('facs-error').textContent = text;
  $('facs-error').hidden = !text;
}

const sha256 = async (bytes) => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
  .map((b) => b.toString(16).padStart(2, '0')).join('');

function showScan({ remember = true } = {}) {
  showFacsError('');
  if (pdf) {
    pdf.loadingTask.destroy();
    pdf = null;
    forgetPdf();
  }
  scanImages = new Map();
  if (remember) {
    try { localStorage.setItem(SCAN_CONFIRMED, '1'); } catch { /* not remembered */ }
  }
  $('facs-warning').hidden = true;
  $('facs-intro').hidden = true;
  $('facs-view').hidden = false;
  renderFacsimile();
}

const forgetConfirmation = () => {
  try { localStorage.removeItem(SCAN_CONFIRMED); } catch { /* nothing stored */ }
};

// Each page image is checked against its hash in pages.json before it is drawn.
function scanImage(surface) {
  const images = scanImages;
  if (!images.has(surface.file)) {
    images.set(surface.file, (async () => {
      const response = await fetch(SCAN_URL + surface.file);
      if (!response.ok) throw new Error(`${surface.file}: HTTP ${response.status}`);
      const bytes = await response.arrayBuffer();
      if (await sha256(bytes) !== surface.sha256) throw new Error(`${surface.file} differs from the page image the zones were measured on.`);
      return createImageBitmap(new Blob([bytes], { type: 'image/png' }));
    })().catch((error) => {
      images.delete(surface.file);
      throw error;
    }));
  }
  return images.get(surface.file);
}

async function openPdf(bytes, name, { remember = true } = {}) {
  showFacsError('');
  try {
    const pages = await pagesReady;
    const hash = await sha256(bytes);
    const pdfjs = await import(`${PDFJS_URL}build/pdf.min.mjs`);
    pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS_URL}build/pdf.worker.min.mjs`;
    // pdf.js transfers the buffer it is given to its worker; keep our copy.
    const doc = await pdfjs.getDocument({ data: bytes.slice(), wasmUrl: `${PDFJS_URL}wasm/` }).promise;
    if (doc.numPages !== pages.pages.length) {
      doc.loadingTask.destroy();
      throw new Error(`“${name}” has ${doc.numPages} page${doc.numPages === 1 ? '' : 's'}; the IMSLP file has ${pages.pages.length}. Is it the right PDF?`);
    }
    pdf = doc;
    scanImages = null;
    forgetConfirmation();
    const warning = $('facs-warning');
    warning.hidden = hash === pages.pdf_sha256;
    warning.textContent = `This PDF differs from the IMSLP file the zones were measured on (SHA-256 ${hash.slice(0, 12)}…, expected ${pages.pdf_sha256.slice(0, 12)}…). The bar outlines may not line up.`;
    $('facs-intro').hidden = true;
    $('facs-view').hidden = false;
    if (remember) storePdf(bytes, name);
    renderFacsimile();
  } catch (error) {
    showFacsError(error.message);
  }
}

async function renderFacsimile() {
  const model = current();
  if (!(pdf || scanImages) || !model) return;
  const token = ++facsToken;
  const surface = model.surfaces.get(model.pages[state.page - 1]?.surface);
  if (!surface?.pdfPage) return;
  const canvas = $('facs-canvas');
  // The page fixes the canvas's shape, so its layout does not depend on the bitmap size.
  canvas.style.aspectRatio = `${surface.width} / ${surface.height}`;
  const [width, height] = await devicePixelSize(canvas);
  if (token !== facsToken || !width) return;
  let scratch;
  try {
    scratch = scanImages ? await drawScanImage(surface, width, height) : await drawPdfPage(surface, width, height, token);
  } catch (error) {
    if (token === facsToken) showFacsError(error.message);
    return;
  }
  if (!scratch || token !== facsToken) return;
  showFacsError('');
  canvas.width = scratch.width;
  canvas.height = scratch.height;
  canvas.getContext('2d').drawImage(scratch, 0, 0);
  // Zones are in pixels of the 300 dpi page images; the viewBox scales them by width.
  const zones = $('zones');
  zones.setAttribute('viewBox', `0 0 ${surface.width} ${surface.height}`);
  zones.replaceChildren(...[...model.zones.values()]
    .filter((z) => model.surfaces.get(z.surface) === surface && z.measure)
    .map((z) => {
      const rect = svgElement('rect', { x: z.x, y: z.y, width: z.w, height: z.h });
      rect.dataset.measure = z.measure;
      if (model.noted.has(z.measure)) rect.classList.add('has-note');
      return rect;
    }));
  $('facs-label').textContent = scanImages ? `Printed page ${surface.printed}` : `Printed page ${surface.printed} (PDF page ${surface.pdfPage})`;
  applyHighlights();
  applyPlaying();
}

// A bitmap the size of the canvas box in device pixels is shown 1:1; any other size is
// resampled by the browser, which blurs the scan at fractional scales such as 1.25 or 1.5.
function devicePixelSize(canvas) {
  return new Promise((resolve) => {
    const observer = new ResizeObserver(([entry]) => {
      observer.disconnect();
      resolve(entryPixels(entry));
    });
    observeDevicePixels(observer, canvas);
  });
}

function entryPixels(entry) {
  const box = entry.devicePixelContentBoxSize?.[0];
  if (box) return [box.inlineSize, box.blockSize];
  const ratio = window.devicePixelRatio || 1;
  return [Math.round(entry.contentRect.width * ratio), Math.round(entry.contentRect.height * ratio)];
}

function observeDevicePixels(observer, element) {
  try {
    observer.observe(element, { box: 'device-pixel-content-box' });
  } catch {
    observer.observe(element); // no device-pixel box (Safari): fall back to CSS pixels × ratio
  }
}

// Both return an off-screen canvas `width` × `height`, or null when a newer render has taken over.
async function drawPdfPage(surface, width, height, token) {
  const page = await pdf.getPage(surface.pdfPage);
  if (token !== facsToken) return null;
  const viewport = page.getViewport({ scale: width / page.getViewport({ scale: 1 }).width });
  renderTask?.cancel();
  const scratch = document.createElement('canvas');
  scratch.width = width;
  scratch.height = height;
  renderTask = page.render({ canvas: scratch, viewport });
  try {
    await renderTask.promise;
  } catch (error) {
    if (error?.name === 'RenderingCancelledException') return null;
    throw error;
  }
  return scratch;
}

async function drawScanImage(surface, width, height) {
  const image = await scanImage(surface);
  const scratch = document.createElement('canvas');
  scratch.width = width;
  scratch.height = height;
  const context = scratch.getContext('2d');
  context.imageSmoothingQuality = 'high';
  context.drawImage(image, 0, 0, scratch.width, scratch.height);
  return scratch;
}

function closeScan() {
  pdf?.loadingTask.destroy();
  pdf = null;
  scanImages = null;
  forgetPdf();
  forgetConfirmation();
  $('facs-view').hidden = true;
  $('facs-intro').hidden = false;
  $('pdf-input').value = '';
}

// The chosen PDF is kept in this browser's IndexedDB so a reload shows it again.
function withStore(mode, action) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(STORE.db, 1);
    open.onupgradeneeded = () => open.result.createObjectStore(STORE.store);
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const request = action(open.result.transaction(STORE.store, mode).objectStore(STORE.store));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    };
  });
}
const storePdf = (bytes, name) => withStore('readwrite', (s) => s.put({ bytes, name }, STORE.key)).catch(() => {});
const forgetPdf = () => withStore('readwrite', (s) => s.delete(STORE.key)).catch(() => {});
async function restorePdf() {
  try {
    const saved = await withStore('readonly', (s) => s.get(STORE.key));
    if (saved?.bytes) await openPdf(saved.bytes, saved.name, { remember: false });
  } catch { /* storage unavailable: the visitor opens the file again */ }
}
function restoreScan() {
  let confirmed = false;
  try { confirmed = localStorage.getItem(SCAN_CONFIRMED) === '1'; } catch { /* storage blocked */ }
  if (confirmed) showScan({ remember: false });
  else restorePdf();
}

// ---------------------------------------------------------------- wiring

async function applyHash() {
  const match = /^#(I{1,3})(?:\/(\d+))?$/.exec(location.hash);
  await showMovement(match ? match[1] : state.mvt || 'I');
  if (match?.[2] === undefined) return;
  const bar = String(Number(match[2]));
  const id = current().byN.get(bar);
  if (id) pin(id, { hash: false });
  else setStatus(`Movement ${state.mvt} has no bar ${bar}.`);
}

function readSettings() {
  for (const [name, key] of Object.entries(SETTINGS)) {
    try { settings[name] = localStorage.getItem(key) === '1'; } catch { /* storage blocked: defaults */ }
  }
  try {
    const percent = Number(localStorage.getItem(PLAYBACK_SETTINGS.tempo));
    if (percent >= 25 && percent <= 200) playback.percent = percent;
    playback.repeats = localStorage.getItem(PLAYBACK_SETTINGS.repeats) !== '0';
  } catch { /* storage blocked: defaults */ }
  $('playback').checked = settings.playback;
  $('mark-notes').checked = settings.markNotes;
  $('measure-boxes').checked = settings.measureBoxes;
  $('tempo').value = $('tempo-number').value = playback.percent;
  $('repeats').checked = playback.repeats;
}

function changeSetting(name, value) {
  settings[name] = value;
  if (name === 'playback' && !value) stopPlayback();
  try { localStorage.setItem(SETTINGS[name], value ? '1' : '0'); } catch { /* not remembered */ }
  applySettings();
}

function bindUi() {
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => { location.hash = `#${b.dataset.mvt}`; }));
  $('prev').addEventListener('click', () => { stopFollowing(); showPage(state.page - 1); });
  $('next').addEventListener('click', () => { stopFollowing(); showPage(state.page + 1); });
  $('play').addEventListener('click', togglePlayback);
  $('stop').addEventListener('click', () => stopPlayback());
  $('tempo').addEventListener('input', (e) => setGlobalTempo(Number(e.target.value)));
  // Applied on Enter, leaving the box or the spin arrows; out-of-range values are clamped.
  $('tempo-number').addEventListener('change', (e) => {
    const v = Math.round(Number(e.target.value));
    setGlobalTempo(e.target.value === '' || !Number.isFinite(v) ? playback.percent : Math.max(25, Math.min(200, v)));
  });
  $('repeats').addEventListener('change', (e) => setRepeats(e.target.checked));
  $('playback').addEventListener('change', (e) => changeSetting('playback', e.target.checked));
  $('mark-notes').addEventListener('change', (e) => changeSetting('markNotes', e.target.checked));
  $('measure-boxes').addEventListener('change', (e) => changeSetting('measureBoxes', e.target.checked));
  document.addEventListener('keydown', (e) => {
    if (!current() || e.altKey || e.ctrlKey || e.metaKey || e.target.closest('input, textarea')) return;
    if (settings.playback && e.code === 'Space' && !e.target.closest('button')) { e.preventDefault(); togglePlayback(); }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      stopFollowing();
      showPage(state.page + (e.key === 'ArrowLeft' ? -1 : 1));
    }
  });
  window.addEventListener('hashchange', () => applyHash().catch((e) => scoreMessage(e.message)));

  const score = $('score');
  score.addEventListener('mouseover', (e) => inspect(e.target));
  score.addEventListener('mouseleave', () => hover(null));
  score.addEventListener('click', (e) => {
    stopFollowing();
    const id = current() && sourceElement(e.target);
    const measure = id && current().ids.get(id).measure;
    if (measure) pin(measure);
  });

  $('annots').addEventListener('click', (e) => {
    const button = e.target.closest('button[data-annot]');
    if (button) selectAnnot(button.dataset.annot);
  });

  const zones = $('zones');
  zones.addEventListener('mouseover', (e) => {
    const measure = current()?.measures.get(e.target.dataset?.measure);
    if (!measure) return;
    hover(measure.id, measure.id);
    setStatus(`Bar ${measure.n}, zone`, measure.zone);
  });
  zones.addEventListener('mouseleave', () => hover(null));
  zones.addEventListener('click', (e) => {
    stopFollowing();
    if (e.target.dataset?.measure) pin(e.target.dataset.measure);
  });

  const pickFile = async (file) => { if (file) await openPdf(await file.arrayBuffer(), file.name); };
  $('pdf-input').addEventListener('change', (e) => pickFile(e.target.files[0]));
  $('scan-show').addEventListener('click', () => showScan());
  $('scan-close').addEventListener('click', closeScan);
  const facs = $('facs');
  facs.addEventListener('dragover', (e) => { e.preventDefault(); facs.classList.add('is-dragover'); });
  facs.addEventListener('dragleave', () => facs.classList.remove('is-dragover'));
  facs.addEventListener('drop', (e) => {
    e.preventDefault();
    facs.classList.remove('is-dragover');
    pickFile(e.dataTransfer.files[0]);
  });
  const canvas = $('facs-canvas');
  observeDevicePixels(new ResizeObserver(([entry]) => {
    const [width, height] = entryPixels(entry);
    if (width && (width !== canvas.width || height !== canvas.height)) renderFacsimile();
  }), canvas);
}

async function main() {
  readSettings();
  bindUi();
  applySettings();
  try {
    toolkit = await loadVerovio();
    toolkit.setOptions({ ...VEROVIO_OPTIONS, expandNever: !playback.repeats });
    $('player').dataset.repeats = String(playback.repeats);
    $('verovio-version').textContent = toolkit.getVersion();
    await applyHash();
  } catch (error) {
    scoreMessage(error.message);
    return;
  }
  restoreScan();
}

main();
