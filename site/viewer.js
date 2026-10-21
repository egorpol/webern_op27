// Webern Op. 27 viewer: the MEI rendered by Verovio with the encoded page and
// system breaks, the editorial notes, and the scan: the page images of
// webern_op27-facsimile, once the visitor confirms that the print is in the
// public domain where they are, or their own copy of the IMSLP PDF. Zones come
// from the MEI.

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
const SETTINGS = { markNotes: 'webern-op27-mark-notes', measureBoxes: 'webern-op27-measure-boxes' };

const $ = (id) => document.getElementById(id);
const xmlId = (el) => el.getAttributeNS(XML_NS, 'id');
const refs = (value) => (value || '').split(/\s+/).filter(Boolean).map((v) => v.replace(/^#/, ''));

const state = { mvt: null, model: null, page: 1, pinned: null, annot: null };
const settings = { markNotes: false, measureBoxes: false };
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
  model.annots = annots.map((el) => {
    const targets = refs(el.getAttribute('plist'));
    const bars = [...new Set([xmlId(el), ...targets].map((t) => model.ids.get(t)?.measure).filter(Boolean))]
      .map((m) => model.measures.get(m))
      .sort((a, b) => Number(a.n) - Number(b.n));
    bars.forEach((bar) => model.noted.add(bar.id));
    return { id: xmlId(el), label: el.getAttribute('label') || el.getAttribute('type'), targets, bars, paras: [...el.getElementsByTagName('p')] };
  });
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
  if (state.mvt === key) return;
  const token = ++mvtToken;
  scoreMessage(`Loading movement ${key}…`);
  const model = await getModel(key);
  if (token !== mvtToken) return;
  toolkit.loadData(model.text);
  model.pageCount = toolkit.getPageCount();
  Object.assign(state, { mvt: key, model, pinned: null, annot: null });
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
  renderFacsimile();
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
  applyHighlights();
}

function pin(measureId, { hash = true } = {}) {
  const model = current();
  const measure = model.measures.get(measureId);
  if (!measure) return;
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
  const pixels = (canvas.parentElement.clientWidth || 600) * (window.devicePixelRatio || 1);
  let scratch;
  try {
    scratch = scanImages ? await drawScanImage(surface, pixels) : await drawPdfPage(surface, pixels, token);
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
}

// Both return an off-screen canvas `pixels` wide, or null when a newer render has taken over.
async function drawPdfPage(surface, pixels, token) {
  const page = await pdf.getPage(surface.pdfPage);
  if (token !== facsToken) return null;
  const viewport = page.getViewport({ scale: pixels / page.getViewport({ scale: 1 }).width });
  renderTask?.cancel();
  const scratch = document.createElement('canvas');
  scratch.width = Math.round(viewport.width);
  scratch.height = Math.round(viewport.height);
  renderTask = page.render({ canvas: scratch, viewport });
  try {
    await renderTask.promise;
  } catch (error) {
    if (error?.name === 'RenderingCancelledException') return null;
    throw error;
  }
  return scratch;
}

async function drawScanImage(surface, pixels) {
  const image = await scanImage(surface);
  const scratch = document.createElement('canvas');
  scratch.width = Math.round(pixels);
  scratch.height = Math.round((image.height * pixels) / image.width);
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
  $('mark-notes').checked = settings.markNotes;
  $('measure-boxes').checked = settings.measureBoxes;
}

function changeSetting(name, value) {
  settings[name] = value;
  try { localStorage.setItem(SETTINGS[name], value ? '1' : '0'); } catch { /* not remembered */ }
  applySettings();
}

function bindUi() {
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => { location.hash = `#${b.dataset.mvt}`; }));
  $('prev').addEventListener('click', () => showPage(state.page - 1));
  $('next').addEventListener('click', () => showPage(state.page + 1));
  $('mark-notes').addEventListener('change', (e) => changeSetting('markNotes', e.target.checked));
  $('measure-boxes').addEventListener('change', (e) => changeSetting('measureBoxes', e.target.checked));
  document.addEventListener('keydown', (e) => {
    if (!current() || e.altKey || e.ctrlKey || e.metaKey || e.target.closest('input, textarea')) return;
    if (e.key === 'ArrowLeft') showPage(state.page - 1);
    if (e.key === 'ArrowRight') showPage(state.page + 1);
  });
  window.addEventListener('hashchange', () => applyHash().catch((e) => scoreMessage(e.message)));

  const score = $('score');
  score.addEventListener('mouseover', (e) => inspect(e.target));
  score.addEventListener('mouseleave', () => hover(null));
  score.addEventListener('click', (e) => {
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
  zones.addEventListener('click', (e) => { if (e.target.dataset?.measure) pin(e.target.dataset.measure); });

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
  let lastWidth = 0;
  new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width);
    if (width !== lastWidth) { lastWidth = width; renderFacsimile(); }
  }).observe(facs);
}

async function main() {
  readSettings();
  bindUi();
  applySettings();
  try {
    toolkit = await loadVerovio();
    toolkit.setOptions(VEROVIO_OPTIONS);
    $('verovio-version').textContent = toolkit.getVersion();
    await applyHash();
  } catch (error) {
    scoreMessage(error.message);
    return;
  }
  restoreScan();
}

main();
