// node --experimental-vm-modules --test tests/test_web_video.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function loadModule(name, globals = {}) {
    const context = vm.createContext({ console, URL, Blob, AbortController, ...globals });
    const cache = new Map();
    async function load(filename) {
        if (cache.has(filename)) return cache.get(filename);
        const module = new vm.SourceTextModule(fs.readFileSync(filename, 'utf8'), { context, identifier: filename });
        cache.set(filename, module);
        await module.link((specifier, parent) => load(path.resolve(path.dirname(parent.identifier), specifier)));
        return module;
    }
    const module = await load(path.resolve(__dirname, '../web_app/frontend/static/js/features', name));
    await module.evaluate();
    return module.namespace;
}
const plain = value => JSON.parse(JSON.stringify(value));

test('video queue retains selected file after filtering and deduplication', async () => {
    const mod = await loadModule('videoPlayerContext.js');
    const result = mod.normalizeVideoContext({ playlist: [null, 'D:\\a.MP4', 'D:/a.MP4', 'D:/b.mp4', 'sound.mp3'], currentIndex: 3 });
    assert.deepEqual(plain(result), { playlist: ['D:/a.MP4', 'D:/b.mp4'], availableFiles: ['D:/a.MP4', 'D:/b.mp4'], currentIndex: 1 });
    assert.equal(mod.normalizeVideoContext({}), null);
});

test('video context is separate from audio, retains add candidates and handles storage failure', async () => {
    const storage = new Map([['tag2file.audioPlayer.context', 'audio']]);
    const mod = await loadModule('videoPlayerContext.js', { sessionStorage: {
        getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value),
    } });
    assert.equal(mod.saveVideoPlayerContext({ playlist: [], availableFiles: ['one.mp4'], currentIndex: -1 }), true);
    assert.deepEqual(plain(mod.loadVideoPlayerContext()), { playlist: [], availableFiles: ['one.mp4'], currentIndex: -1 });
    assert.equal(storage.get('tag2file.audioPlayer.context'), 'audio');
    storage.set('tag2file.videoPlayer.context', 'broken');
    assert.equal(mod.loadVideoPlayerContext(), null);
    const denied = await loadModule('videoPlayerContext.js', { sessionStorage: {
        getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); },
    } });
    assert.equal(denied.loadVideoPlayerContext(), null);
    assert.equal(denied.saveVideoPlayerContext({ playlist: ['one.mp4'] }), false);
});

test('shared audio navigation wraps, random excludes current, and empty/single queues are safe', async () => {
    const mod = await loadModule('videoPlayerContext.js');
    for (const mode of [0, 2]) {
        assert.equal(mod.getAdjacentPlaylistIndex(mode, 3, 2, 1), 0);
        assert.equal(mod.getAdjacentPlaylistIndex(mode, 3, 0, -1), 2);
    }
    for (let i = 0; i < 20; i++) assert.notEqual(mod.getAdjacentPlaylistIndex(1, 3, 1, 1), 1);
    for (const mode of [0, 1, 2]) {
        assert.equal(mod.getAdjacentPlaylistIndex(mode, 0, -1), -1);
        assert.equal(mod.getAdjacentPlaylistIndex(mode, 1, 0), 0);
    }
    assert.equal(mod.formatVideoTime(3661.7), '1:01:01');
    assert.equal(mod.formatVideoTime(Infinity), '00:00');
});

test('new audio and video tabs own independent queues and retain them after reload', async () => {
    const storage = () => {
        const values = new Map();
        return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
    };
    for (const type of ['audio', 'video']) {
        const moduleName = `${type}PlayerContext.js`;
        const suffix = type === 'audio' ? '.mp3' : '.mp4';
        const save = type === 'audio' ? 'saveAudioPlayerContext' : 'saveVideoPlayerContext';
        const load = type === 'audio' ? 'loadAudioPlayerContext' : 'loadVideoPlayerContext';
        const parentStorage = storage();
        const firstTab = storage();
        const secondTab = storage();
        const parent = await loadModule(moduleName, { sessionStorage: parentStorage });
        const playlist = ['中文 #1%', 'other'].map(name => `D:/${name}${suffix}`);
        assert.equal(parent[save]({ playlist, currentIndex: 0 }, firstTab), true);
        assert.equal(parent[save]({ playlist, currentIndex: 1 }, secondTab), true);
        assert.equal(parent[load](), null);
        const first = await loadModule(moduleName, { sessionStorage: firstTab });
        const second = await loadModule(moduleName, { sessionStorage: secondTab });
        assert.deepEqual(plain(first[load]().playlist), playlist);
        assert.equal(first[load]().currentIndex, 0);
        assert.equal(second[load]().currentIndex, 1);
        first[save]({ playlist: ['changed' + suffix], currentIndex: 0 });
        const reloaded = await loadModule(moduleName, { sessionStorage: secondTab });
        assert.deepEqual(plain(reloaded[load]().playlist), playlist);
        assert.equal(reloaded[load]().currentIndex, 1);
        assert.equal(parent[save]({ playlist }, { setItem() { throw new Error('denied'); } }), false);
    }
});

async function subtitleHarness() {
    const pending = [];
    const revoked = [];
    let nextURL = 0;
    const tracks = [];
    const mod = await loadModule('videoPlayerSubtitles.js', {
        fetch: (url, options) => new Promise(resolve => pending.push({ url, options, resolve })),
        URL: { createObjectURL: () => `blob:${++nextURL}`, revokeObjectURL: value => revoked.push(value) },
        FormData: class { append() {} },
        document: { createElement: () => ({
            track: { mode: 'disabled', activeCues: [{ getCueAsHTML: () => ({ textContent: '字幕\nEnglish' }) }], addEventListener() {} }, listeners: {},
            addEventListener(event, fn) { this.listeners[event] = fn; },
            remove() { tracks.splice(tracks.indexOf(this), 1); },
        }) },
    });
    const subtitles = new mod.VideoSubtitles({ append: element => tracks.push(element) }, () => {});
    const settle = async (index, data, ok = true) => {
        pending[index].resolve({ ok, json: async () => data });
        await new Promise(resolve => setImmediate(resolve));
    };
    const caption = name => ({ exists: true, name, content: 'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nTest\n' });
    return { subtitles, pending, settle, caption, tracks, revoked };
}

async function keyboardHarness() {
    const mod = await loadModule('videoPlayer.js', { document: { getElementById: () => null } });
    const player = Object.create(mod.WebVideoPlayer.prototype);
    Object.assign(player, {
        video: { currentTime: 12, duration: 20, paused: true },
        playlist: ['one.mp4', 'two.mp4'], currentIndex: 0,
        el: { 'add-dialog': { open: false } },
        updateTimeline() {}, showControls() {},
        adjacent(direction) { this.lastDirection = direction; },
    });
    const press = (key, options = {}) => {
        const event = { key, code: key, target: { tagName: 'DIV', closest: () => null },
            preventDefault() { this.defaultPrevented = true; }, ...options };
        player.keydown(event);
        return event;
    };
    return { player, press };
}

test('video arrows seek five seconds, clamp boundaries and keep paused state', async () => {
    const { player, press } = await keyboardHarness();
    assert.equal(press('ArrowLeft').defaultPrevented, true);
    assert.equal(player.video.currentTime, 7);
    press('ArrowRight');
    assert.equal(player.video.currentTime, 12);
    player.video.currentTime = 2;
    press('ArrowLeft');
    assert.equal(player.video.currentTime, 0);
    player.video.currentTime = 18;
    press('ArrowRight');
    assert.equal(player.video.currentTime, 20);
    assert.equal(player.video.paused, true);
    assert.equal(player.currentIndex, 0);
    player.failed = true;
    press('ArrowLeft');
    assert.equal(player.video.currentTime, 20);
    player.failed = false;
    player.video.duration = NaN;
    press('ArrowLeft');
    assert.equal(player.video.currentTime, 20);
});

test('video arrows preserve playlist shortcuts, browser navigation and editable controls', async () => {
    const { player, press } = await keyboardHarness();
    press('ArrowLeft', { ctrlKey: true });
    assert.equal(player.lastDirection, -1);
    press('ArrowRight', { ctrlKey: true });
    assert.equal(player.lastDirection, 1);
    for (const options of [
        { altKey: true }, { metaKey: true }, { shiftKey: true },
        { target: { isContentEditable: true } },
        { target: { tagName: 'INPUT', closest: () => ({ id: 'volume' }) } },
    ]) assert.notEqual(press('ArrowLeft', options).defaultPrevented, true);
    player.el['add-dialog'].open = true;
    assert.notEqual(press('ArrowRight').defaultPrevented, true);
    assert.equal(player.video.currentTime, 12);
    player.el['add-dialog'].open = false;
    press('ArrowRight', { target: { tagName: 'INPUT', closest: () => null } });
    assert.equal(player.video.currentTime, 17);
});

test('late subtitle responses cannot overwrite a new video and resources are revoked', async () => {
    const h = await subtitleHarness();
    h.subtitles.activate('A.mp4');
    h.subtitles.activate('B.mp4');
    assert.equal(h.pending[0].options.signal.aborted, true);
    await h.settle(1, h.caption('B.srt'));
    await h.settle(0, h.caption('A.srt'));
    assert.equal(h.subtitles.status, 'B.srt');
    assert.equal(h.tracks.length, 1);
    h.subtitles.setEnabled(false);
    assert.equal(h.tracks[0].track.mode, 'hidden');
    assert.equal(h.subtitles.text(), '');
    h.subtitles.setEnabled(true);
    assert.equal(h.subtitles.text(), '字幕\nEnglish');
    h.subtitles.setNativeFullscreen(true);
    assert.equal(h.subtitles.text(), '');
    assert.equal(h.tracks[0].track.mode, 'showing');
    h.subtitles.setNativeFullscreen(false);
    assert.equal(h.subtitles.text(), '字幕\nEnglish');
    h.subtitles.activate(null);
    assert.equal(h.tracks.length, 0);
    assert.deepEqual(h.revoked, ['blob:1']);
});

test('manual subtitle overrides survive video switching and failures keep existing captions', async () => {
    const h = await subtitleHarness();
    h.subtitles.activate('A.mp4');
    await h.settle(0, h.caption('auto.srt'));
    const load = h.subtitles.load({ name: 'manual.srt', size: 50 });
    await h.settle(1, h.caption('manual.srt'));
    await load;
    const failed = h.subtitles.load({ name: 'bad.srt', size: 50 });
    await h.settle(2, { message: '无法解析' }, false);
    await failed;
    assert.match(h.subtitles.status, /保留当前字幕/);
    assert.equal(h.tracks[0].label, 'manual.srt');
    h.subtitles.activate('B.mp4');
    h.subtitles.setEnabled(false);
    h.subtitles.activate('A.mp4');
    assert.equal(h.subtitles.status, 'manual.srt');
    assert.equal(h.tracks[0].track.mode, 'hidden');
    await h.settle(3, h.caption('late-B.srt'));
    assert.equal(h.subtitles.status, 'manual.srt');
});
