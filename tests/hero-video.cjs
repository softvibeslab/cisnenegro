// Run from any directory: node tests/hero-video.cjs
// Behavioral checks with controllable browser media promises; no browser or dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'sitio/assets/js/hero-video.js'), 'utf8');
const markup = fs.readFileSync(path.join(root, 'sitio/con-video/index.html'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(name, fn) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(fn);
  }
  emit(name, event = {}) { for (const fn of this.listeners.get(name) || []) fn(event); }
}

function harness(options = {}) {
  const motion = Object.assign(new Events(), { matches: !!options.reducedMotion });
  const connection = Object.assign(new Events(), { saveData: !!options.saveData });
  const document = Object.assign(new Events(), { hidden: !!options.hidden });
  const label = { textContent: 'Reproducir video' };
  const icon = { textContent: '▶' };
  const button = Object.assign(new Events(), {
    hidden: true,
    querySelector(selector) { return selector === '[data-video-label]' ? label : icon; }
  });
  const classes = new Set();
  const video = Object.assign(new Events(), {
    paused: true,
    muted: false,
    defaultMuted: false,
    dataset: { src: '/desktop.mp4', mobileSrc: '/mobile.mp4' },
    src: '',
    loads: 0,
    plays: 0,
    pendingAttempt: null,
    classList: { add: name => classes.add(name), remove: name => classes.delete(name) },
    getAttribute(name) { return name === 'src' ? this.src || null : null; },
    load() { this.loads++; },
    play() {
      this.plays++;
      this.paused = false; // Native play() clears paused before the playing event.
      return new Promise((resolve, reject) => { this.pendingAttempt = { resolve, reject }; });
    },
    pause() {
      const changed = !this.paused;
      this.paused = true;
      if (changed) this.emit('pause');
      const attempt = this.pendingAttempt;
      if (attempt) {
        this.pendingAttempt = null;
        // A pause interrupts an outstanding play promise asynchronously.
        queueMicrotask(() => attempt.reject(Object.assign(new Error('Playback interrupted'), { name: 'AbortError' })));
      }
    }
  });
  const hero = {
    querySelector: selector => selector === 'video' ? video : button,
    getBoundingClientRect: () => options.offscreen ? { top: 1100, bottom: 1900 } : { top: 80, bottom: 900 }
  };
  document.querySelector = () => options.missingHero ? null : hero;
  let observer;
  class IntersectionObserver {
    constructor(callback) { observer = callback; }
    observe() {}
  }
  const window = {
    innerHeight: 1000,
    matchMedia: query => query.includes('prefers-reduced-motion') ? motion : { matches: !!options.mobile }
  };
  if (!options.withoutObserver) window.IntersectionObserver = IntersectionObserver;
  vm.runInNewContext(source, { window, document, navigator: { connection }, IntersectionObserver, Promise });

  return {
    video, button, label, icon, classes,
    click: () => button.emit('click'),
    intersect: visible => observer([{ isIntersecting: visible }]),
    visibility(hidden) { document.hidden = hidden; document.emit('visibilitychange'); },
    preference(reduced) { motion.matches = reduced; motion.emit('change'); },
    saveData(value) { connection.saveData = value; connection.emit('change'); },
    start() {
      const attempt = video.pendingAttempt;
      assert.ok(attempt, 'A play attempt must be waiting');
      video.pendingAttempt = null;
      video.paused = false;
      video.emit('playing');
      attempt.resolve();
    },
    reject(name = 'NotAllowedError') {
      const attempt = video.pendingAttempt;
      assert.ok(attempt, 'A play attempt must be waiting');
      video.pendingAttempt = null;
      video.paused = true;
      attempt.reject(Object.assign(new Error('Playback rejected'), { name }));
    },
    error: () => video.emit('error')
  };
}

const cases = [
  ['static fallback does not fetch video without JavaScript', async () => {
    const video = markup.match(/<video\b[\s\S]*?<\/video>/)[0];
    assert.match(video, /\bmuted\b/);
    assert.match(video, /\bloop\b/);
    assert.match(video, /\bplaysinline\b/);
    assert.match(video, /preload="none"/);
    assert.doesNotMatch(video, /\s(?:src|autoplay)\s*=/);
    assert.match(markup, /<img[^>]+hero__poster[^>]+neon\.jpg/);
    assert.match(markup, /<button[^>]+hero__video-control[^>]+\bhidden\b/);
  }],
  ['desktop loads one muted source and reveals only after playing', async () => {
    const h = harness();
    assert.equal(h.video.src, '/desktop.mp4');
    assert.equal(h.video.loads, 1);
    assert.equal(h.video.muted, true);
    assert.equal(h.video.defaultMuted, true);
    assert.equal(h.classes.has('is-ready'), false);
    h.start(); await flush();
    assert.equal(h.classes.has('is-ready'), true);
    assert.equal(h.label.textContent, 'Pausar video');
    assert.equal(h.button.hidden, false);
  }],
  ['mobile loads only its lighter source', async () => {
    const h = harness({ mobile: true });
    assert.equal(h.video.src, '/mobile.mp4');
    assert.equal(h.video.loads, 1);
    h.start(); await flush();
  }],
  ['offscreen and hidden startup defer all media loading', async () => {
    for (const option of ['offscreen', 'hidden']) {
      const h = harness({ [option]: true });
      assert.equal(h.video.src, '', option);
      assert.equal(h.video.plays, 0, option);
      if (option === 'offscreen') h.intersect(true); else h.visibility(false);
      assert.equal(h.video.loads, 1, option);
      h.start(); await flush();
    }
  }],
  ['reduced motion and data saving defer media until explicit opt-in', async () => {
    for (const option of ['reducedMotion', 'saveData']) {
      const h = harness({ [option]: true });
      assert.equal(h.video.src, '', option);
      h.intersect(true); h.visibility(false);
      assert.equal(h.video.plays, 0, option);
      h.click();
      assert.equal(h.video.loads, 1, option);
      h.start(); await flush();
      assert.equal(h.video.paused, false, option);
    }
  }],
  ['preference changes restore the image and stop running media', async () => {
    for (const update of ['preference', 'saveData']) {
      const h = harness(); h.start(); await flush();
      h[update](true);
      assert.equal(h.video.paused, true, update);
      assert.equal(h.classes.has('is-ready'), false, update);
      assert.equal(h.label.textContent, 'Reproducir video', update);
      h.intersect(false); h.intersect(true); h.visibility(true); h.visibility(false);
      assert.equal(h.video.plays, 1, update);
    }
  }],
  ['manual pause survives viewport and tab changes until explicitly resumed', async () => {
    const h = harness(); h.start(); await flush();
    h.click();
    assert.equal(h.video.paused, true);
    assert.equal(h.label.textContent, 'Reproducir video');
    h.intersect(false); h.intersect(true); h.visibility(true); h.visibility(false);
    assert.equal(h.video.plays, 1);
    h.click(); h.start(); await flush();
    assert.equal(h.video.paused, false);
    assert.equal(h.video.loads, 1);
    assert.equal(h.label.textContent, 'Pausar video');
  }],
  ['ordinary viewport and tab pauses resume automatically', async () => {
    const h = harness(); h.start(); await flush();
    h.intersect(false);
    assert.equal(h.video.paused, true);
    h.intersect(true); h.start(); await flush();
    h.visibility(true);
    assert.equal(h.video.paused, true);
    h.visibility(false); h.start(); await flush();
    assert.equal(h.video.plays, 3);
    assert.equal(h.video.loads, 1);
  }],
  ['blocked autoplay preserves image and permits a manual retry', async () => {
    const h = harness(); h.reject(); await flush();
    assert.equal(h.classes.has('is-ready'), false);
    assert.equal(h.button.hidden, false);
    assert.equal(h.label.textContent, 'Reproducir video');
    h.intersect(false); h.intersect(true);
    assert.equal(h.video.plays, 1);
    h.click(); h.start(); await flush();
    assert.equal(h.video.paused, false);
    assert.equal(h.classes.has('is-ready'), true);
  }],
  ['media failure removes video and disables automatic retry', async () => {
    const h = harness(); h.start(); await flush();
    h.error();
    assert.equal(h.video.paused, true);
    assert.equal(h.classes.has('is-ready'), false);
    assert.equal(h.button.hidden, true);
    h.intersect(false); h.intersect(true); h.visibility(true); h.visibility(false);
    assert.equal(h.video.plays, 1);
  }],
  ['pending play interrupted by viewport exit can resume on return', async () => {
    const h = harness();
    h.intersect(false);
    await flush();
    h.intersect(true);
    await flush();
    assert.equal(h.video.plays, 2, 'AbortError must not turn an environmental pause into a manual pause');
    h.start(); await flush();
    assert.equal(h.video.paused, false);
  }],
  ['rapid viewport reentry before the old play settles resumes once', async () => {
    const h = harness();
    h.intersect(false); h.intersect(true);
    await flush();
    assert.equal(h.video.plays, 2, 'Finishing an interrupted attempt must reconsider current visibility');
    h.start(); await flush();
    assert.equal(h.classes.has('is-ready'), true);
  }],
  ['pending play interrupted by tab hiding can resume on return', async () => {
    const h = harness();
    h.visibility(true); h.visibility(false);
    await flush();
    assert.equal(h.video.plays, 2, 'Pending playback should resume when tab becomes visible again');
    h.start(); await flush();
  }],
  ['manual pause during pending playback stays paused', async () => {
    const h = harness(); h.click(); await flush();
    h.intersect(false); h.intersect(true); h.visibility(true); h.visibility(false);
    await flush();
    assert.equal(h.video.paused, true);
    assert.equal(h.video.plays, 1);
  }],
  ['missing hero and absent IntersectionObserver do not break startup', async () => {
    const empty = harness({ missingHero: true });
    assert.equal(empty.video.plays, 0);
    const h = harness({ withoutObserver: true }); h.start(); await flush();
    assert.equal(h.video.paused, false);
  }]
];

(async () => {
  let failures = 0;
  for (const [name, run] of cases) {
    try { await run(); console.log('PASS ' + name); }
    catch (error) { failures++; console.error('FAIL ' + name + '\n  ' + error.message); }
  }
  console.log(`${cases.length - failures}/${cases.length} hero-video checks passed.`);
  process.exitCode = failures ? 1 : 0;
})().catch(error => { console.error(error); process.exitCode = 1; });
