// Webern Op. 27 viewer: the MEI rendered by Verovio with the encoded page and
// system breaks, the editorial notes, and the scan from the visitor's own copy
// of the IMSLP PDF. The scan is never hosted here; zones come from the MEI.

const VEROVIO_URL = 'https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js';
const VEROVIO_SRI = 'sha384-7oICD/hf52uWdE8X0lMFqe7iIspaUj3aQjeZUnBQZpxjrZcHtqlRd3C78cje2e19';
// pdf.js 6 decodes this scan's fax-encoded images with wasm/jbig2.wasm, which
// cdnjs does not carry; jsDelivr serves the whole npm package.
const PDFJS_URL = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/';
const REPO_BLOB = 'https://github.com/egorpol/webern_op27/blob/main/';
// The layout of camat_v2's facsimile notebook: one rendered page per printed page.
const VEROVIO_OPTIONS = {
  breaks: 'encoded', adjustPageHeight: true, footer: 'none', svgViewBox: true, condense: 'none',
  scale: 35, spacingLinear: 0.25, spacingNonLinear: 0.6, minLastJustification: 0,
};
const XML_NS = 'http://www.w3.org/XML/1998/namespace';
const STORE = { db: 'webern-op27-viewer', store: 'files', key: 'imslp-pdf' };

const $ = (id) => document.getElementById(id);
const xmlId = (el) => el.getAttributeNS(XML_NS, 'id');
const refs = (value) => (value || '').split(/\s+/).filter(Boolean).map((v) => v.replace(/^#/, ''));

const state = { mvt: null, model: null, page: 1, pinned: null, annot: null };
const models = new Map();
const pagesReady = fetch('facsimiles/ue1937/pages.json').then((r) => {
  if (!r.ok) throw new Error(`facsimiles/ue1937/pages.json: HTTP ${r.status}`);
  return r.json();
});
let toolkit = null;
let pdf = null;
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
    surfaces: new Map(), zones: new Map(), annots: [], svg: new Map(), pageCount: 0,
  };
  const edition = doc.querySelector('editionStmt > edition');
  model.edition = edition ? `${edition.textContent.trim()} (version ${edition.getAttribute('n')})` : '';

  for (const surface of doc.getElementsByTagName('surface')) {
    const graphic = surface.getElementsByTagName('graphic')[0];
    const file = graphic.getAttribute('target').split('/').pop();
    model.surfaces.set(xmlId(surface), {
      width: Number(graphic.getAttribute('width')),
      height: Number(graphic.getAttribute('height')),
      pdfPage: pages.pages.find((p) => p.file === file)?.pdf_page_number,
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
  const printed = model.pages[page - 1]?.n;
  $('page-label').textContent = `${printed ? `p. ${printed}` : 'page'} (${page}/${model.pageCount})`;
  $('prev').disabled = page <= 1;
  $('next').disabled = page >= model.pageCount;
  applyHighlights();
  renderFacsimile();
}

// Every rendered fragment of an element: the element itself and the
// continuations Verovio draws after a system break (class "id-<xml:id>").
function svgNodes(id) {
  return $('score').querySelectorAll(`[id="${CSS.escape(id)}"], .id-${CSS.escape(id)}`);
}

function applyHighlights() {
  document.querySelectorAll('.is-pinned, .is-annot').forEach((n) => n.classList.remove('is-pinned', 'is-annot'));
  if (state.pinned) svgNodes(state.pinned).forEach((n) => n.classList.add('is-pinned'));
  const annot = state.annot && current().annots.find((a) => a.id === state.annot);
  annot?.targets.forEach((t) => svgNodes(t).forEach((n) => n.classList.add('is-annot')));
  for (const rect of $('zones').children) rect.classList.toggle('is-pinned', rect.dataset.measure === state.pinned);
  document.querySelectorAll('.notes li > button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.annot === state.annot)));
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

async function openPdf(bytes, name, { remember = true } = {}) {
  showFacsError('');
  try {
    const pages = await pagesReady;
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    const hash = [...digest].map((b) => b.toString(16).padStart(2, '0')).join('');
    const pdfjs = await import(`${PDFJS_URL}build/pdf.min.mjs`);
    pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS_URL}build/pdf.worker.min.mjs`;
    // pdf.js transfers the buffer it is given to its worker; keep our copy.
    const doc = await pdfjs.getDocument({ data: bytes.slice(), wasmUrl: `${PDFJS_URL}wasm/` }).promise;
    if (doc.numPages !== pages.pages.length) {
      doc.loadingTask.destroy();
      throw new Error(`“${name}” has ${doc.numPages} page${doc.numPages === 1 ? '' : 's'}; the IMSLP file has ${pages.pages.length}. Is it the right PDF?`);
    }
    pdf = doc;
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
  if (!pdf || !model) return;
  const token = ++facsToken;
  const surface = model.surfaces.get(model.pages[state.page - 1]?.surface);
  if (!surface?.pdfPage) return;
  const page = await pdf.getPage(surface.pdfPage);
  if (token !== facsToken) return;
  const canvas = $('facs-canvas');
  const cssWidth = canvas.parentElement.clientWidth || 600;
  const viewport = page.getViewport({ scale: (cssWidth / page.getViewport({ scale: 1 }).width) * (window.devicePixelRatio || 1) });
  renderTask?.cancel();
  const scratch = document.createElement('canvas');
  scratch.width = Math.round(viewport.width);
  scratch.height = Math.round(viewport.height);
  renderTask = page.render({ canvas: scratch, viewport });
  try {
    await renderTask.promise;
  } catch (error) {
    if (error?.name === 'RenderingCancelledException') return;
    throw error;
  }
  if (token !== facsToken) return;
  canvas.width = scratch.width;
  canvas.height = scratch.height;
  canvas.getContext('2d').drawImage(scratch, 0, 0);
  // Zones are in pixels of the 300 dpi page images; the viewBox scales them by width.
  const zones = $('zones');
  zones.setAttribute('viewBox', `0 0 ${surface.width} ${surface.height}`);
  zones.replaceChildren(...[...model.zones.values()]
    .filter((z) => model.surfaces.get(z.surface) === surface && z.measure)
    .map((z) => {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      Object.entries({ x: z.x, y: z.y, width: z.w, height: z.h }).forEach(([k, v]) => rect.setAttribute(k, v));
      rect.dataset.measure = z.measure;
      return rect;
    }));
  $('facs-label').textContent = `Printed page ${surface.printed} (PDF page ${surface.pdfPage})`;
  applyHighlights();
}

function closePdf() {
  pdf?.loadingTask.destroy();
  pdf = null;
  forgetPdf();
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

function bindUi() {
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => { location.hash = `#${b.dataset.mvt}`; }));
  $('prev').addEventListener('click', () => showPage(state.page - 1));
  $('next').addEventListener('click', () => showPage(state.page + 1));
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
  $('pdf-close').addEventListener('click', closePdf);
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
  bindUi();
  try {
    toolkit = await loadVerovio();
    toolkit.setOptions(VEROVIO_OPTIONS);
    $('verovio-version').textContent = toolkit.getVersion();
    await applyHash();
  } catch (error) {
    scoreMessage(error.message);
    return;
  }
  restorePdf();
}

main();
