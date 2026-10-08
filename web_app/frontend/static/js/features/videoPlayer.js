import { PLAY_MODES, formatVideoTime, getAdjacentPlaylistIndex, loadVideoPlayerContext,
    normalizeVideoContext, saveVideoPlayerContext } from './videoPlayerContext.js';
import { VideoSubtitles } from './videoPlayerSubtitles.js';

const SHAPES = {
    back: '<path d="m14 5-7 7 7 7M7 12h14"/>',
    play: '<path d="m8 5 11 7-11 7Z"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    previous: '<path d="M5 5v14M19 5 8 12l11 7Z"/>',
    next: '<path d="M19 5v14M5 5l11 7-11 7Z"/>',
    repeat: '<path d="m7 3-4 4 4 4M3 7h13a5 5 0 0 1 5 5M17 21l4-4-4-4M21 17H8a5 5 0 0 1-5-5"/>',
    repeat_one: '<path d="m7 3-4 4 4 4M3 7h13a5 5 0 0 1 5 5M17 21l4-4-4-4M21 17H8a5 5 0 0 1-5-5M11 10l2-1v6"/>',
    shuffle: '<path d="M3 6h3c5 0 7 12 12 12h3M3 18h3c5 0 7-12 12-12h3M18 3l3 3-3 3M18 15l3 3-3 3"/>',
    volume: '<path d="M3 9h4l5-4v14l-5-4H3ZM16 8a6 6 0 0 1 0 8M19 5a10 10 0 0 1 0 14"/>',
    mute: '<path d="M3 9h4l5-4v14l-5-4H3ZM16 9l6 6M22 9l-6 6"/>',
    subtitles: '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M10 9a3 3 0 1 0 0 6M19 9a3 3 0 1 0 0 6"/>',
    playlist: '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
    more: '<circle cx="4" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="20" cy="12" r="1"/>',
    fullscreen: '<path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6"/>',
    restore: '<path d="M3 9h6V3M21 9h-6V3M9 21v-6H3M15 21v-6h6"/>',
    add: '<path d="M12 4v16M4 12h16"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    video: '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="m10 8 6 4-6 4Z"/>',
};

function icon(element, name, label = null) {
    // Only fixed application-owned SVG paths are inserted as markup.
    element.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${SHAPES[name]}</svg>`;
    if (label) {
        element.title = label;
        element.setAttribute('aria-label', label);
    }
}

export class WebVideoPlayer {
    constructor(root) {
        this.root = root;
        this.el = Object.fromEntries([...root.querySelectorAll('[id]')].map(element => [element.id, element]));
        root.querySelectorAll('[data-icon]').forEach(element => icon(element, element.dataset.icon));
        this.video = this.el.video;
        this.video.controls = false;
        this.video.volume = 0.7;
        this.lastVolume = 0.7;
        this.playMode = 0;
        this.generation = 0;
        this.subtitles = new VideoSubtitles(this.video, () => this.updateSubtitles());
        this.resizeObserver = new ResizeObserver(() => this.layoutCaptions());
        this.resizeObserver.observe(this.el['video-stage']);
        const direct = new URLSearchParams(location.search).get('path');
        const context = direct ? normalizeVideoContext({ playlist: [direct], currentIndex: 0 }) : loadVideoPlayerContext();
        Object.assign(this, context || { playlist: [], availableFiles: [], currentIndex: -1 });
        this.bindEvents();
        this.renderPlaylist();
        if (this.playlist.length) this.playAt(this.currentIndex);
        else this.updateEmpty();
    }

    bindEvents() {
        const click = (id, handler) => this.el[id].addEventListener('click', handler);
        click('play', () => this.togglePlay());
        click('previous', () => this.adjacent(-1));
        click('next', () => this.adjacent(1));
        click('mode', () => {
            this.playMode = (this.playMode + 1) % PLAY_MODES.length;
            const mode = PLAY_MODES[this.playMode];
            icon(this.el.mode, mode.icon, `${mode.label}（点击切换）`);
        });
        click('mute', () => {
            if (this.video.muted || this.video.volume === 0) {
                if (this.video.volume === 0) this.video.volume = this.lastVolume;
                this.video.muted = false;
            } else this.video.muted = true;
        });
        this.el.volume.addEventListener('input', () => {
            this.video.volume = Number(this.el.volume.value);
            this.video.muted = false;
        });
        this.el.progress.addEventListener('input', () => {
            this.seeking = true;
            this.updateTime(Number(this.el.progress.value));
            this.fillSlider(this.el.progress);
        });
        this.el.progress.addEventListener('change', () => {
            this.seeking = false;
            if (Number.isFinite(this.video.duration)) this.video.currentTime = Number(this.el.progress.value);
            this.showControls();
        });
        click('playlist-toggle', () => this.setPlaylistVisible(this.el['playlist-sidebar'].hidden));
        click('playlist-close', () => this.setPlaylistVisible(false));
        click('fullscreen', () => this.toggleFullscreen());
        this.el['video-stage'].addEventListener('dblclick', () => this.toggleFullscreen());
        this.el['video-stage'].addEventListener('click', () => this.showControls());
        for (const name of ['subtitles', 'more']) click(`${name}-button`, () => this.toggleMenu(name));
        click('load-subtitle', () => {
            this.subtitlePickerPath = this.currentPath();
            this.closeMenus();
            this.el['subtitle-file'].click();
        });
        this.el['subtitle-file'].addEventListener('change', () => {
            const file = this.el['subtitle-file'].files[0];
            if (file && this.subtitlePickerPath === this.currentPath()) this.subtitles.load(file);
            this.el['subtitle-file'].value = '';
        });
        this.el['show-subtitles'].addEventListener('change', event => this.subtitles.setEnabled(event.target.checked));
        click('add-videos', () => this.openAddDialog());
        click('sidebar-add', () => this.openAddDialog());
        click('confirm-add', () => {
            this.el['available-videos'].querySelectorAll('input:checked').forEach(input => {
                if (!this.playlist.includes(input.value)) this.playlist.push(input.value);
            });
            this.el['add-dialog'].close();
            if (this.currentIndex < 0 && this.playlist.length) this.playAt(0);
            else { this.renderPlaylist(); this.saveContext(); }
        });
        this.video.addEventListener('loadedmetadata', () => { this.updateTimeline(); this.layoutCaptions(); this.showStatus(''); });
        this.video.addEventListener('durationchange', () => this.updateTimeline());
        this.video.addEventListener('timeupdate', () => this.updateTimeline());
        this.video.addEventListener('seeked', () => this.updateTimeline());
        this.video.addEventListener('webkitbeginfullscreen', () => this.subtitles.setNativeFullscreen(true));
        this.video.addEventListener('webkitendfullscreen', () => this.subtitles.setNativeFullscreen(false));
        this.video.addEventListener('play', () => { icon(this.el.play, 'pause', '暂停（空格）'); this.showStatus(''); this.showControls(); });
        this.video.addEventListener('pause', () => { icon(this.el.play, 'play', '播放（空格）'); this.showControls(); });
        this.video.addEventListener('ended', () => {
            if (this.failed || !this.playlist.length) return;
            if (this.playMode === 2) { this.video.currentTime = 0; this.tryPlay(); }
            else this.adjacent(1);
        });
        this.video.addEventListener('error', () => this.playbackError());
        this.video.addEventListener('volumechange', () => {
            if (this.video.volume > 0) this.lastVolume = this.video.volume;
            const muted = this.video.muted || this.video.volume === 0;
            icon(this.el.mute, muted ? 'mute' : 'volume', muted ? '恢复音量' : '静音');
            this.el.volume.value = this.video.muted ? 0 : this.video.volume;
            this.fillSlider(this.el.volume);
        });
        document.addEventListener('fullscreenchange', () => this.fullscreenChanged());
        document.addEventListener('keydown', event => this.keydown(event));
        document.addEventListener('pointerdown', event => {
            if (!event.target.closest('.menu-anchor')) this.closeMenus();
        });
        this.root.addEventListener('pointermove', () => this.showControls());
        this.root.addEventListener('focusin', () => this.showControls());
        this.el.controls.addEventListener('pointerdown', () => { this.draggingControl = true; });
        document.addEventListener('pointerup', () => { this.draggingControl = false; this.showControls(); });
        document.addEventListener('pointercancel', () => { this.draggingControl = false; this.seeking = false; });
        window.addEventListener('pagehide', () => { this.video.pause(); this.subtitles.activate(null); clearTimeout(this.controlsTimer); });
        window.addEventListener('pageshow', event => {
            if (event.persisted) this.subtitles.activate(this.currentPath());
        });
    }

    currentPath() { return this.playlist[this.currentIndex] || null; }
    streamURL(path = this.currentPath()) { return `/api/video/stream?path=${encodeURIComponent(path)}`; }
    saveContext() { saveVideoPlayerContext(this); }
    showStatus(text) { this.el['playback-status'].textContent = text; this.el['playback-status'].hidden = !text; }

    playAt(index) {
        if (index < 0 || index >= this.playlist.length) return;
        this.generation++;
        this.video.pause();
        this.currentIndex = index;
        this.failed = false;
        this.seeking = false;
        const path = this.currentPath();
        const name = path.split('/').pop();
        this.el['video-title'].textContent = name;
        this.el['video-title'].title = name;
        document.title = `${name} - 视频播放器`;
        this.el['open-original'].href = this.streamURL();
        this.el.progress.value = 0;
        this.el.progress.disabled = true;
        this.updateTime(0, 0);
        this.fillSlider(this.el.progress);
        this.video.src = this.streamURL();
        this.subtitles.activate(path);
        this.showStatus('正在加载视频…');
        this.renderPlaylist();
        this.saveContext();
        this.tryPlay();
    }

    async tryPlay() {
        const generation = this.generation;
        try { await this.video.play(); }
        catch (error) {
            if (generation !== this.generation || error.name === 'AbortError') return;
            if (error.name === 'NotAllowedError') this.showStatus('点击播放按钮开始播放');
            else this.playbackError();
        }
    }

    async playbackError() {
        if (!this.currentPath() || this.failed) return;
        const generation = this.generation;
        this.failed = true;
        this.el.progress.disabled = true;
        let message = '此视频无法播放，可能是文件损坏或浏览器不支持其编码。可选择下一部或在浏览器中单独打开。';
        this.showStatus(message);
        try {
            const response = await fetch(this.streamURL(), { method: 'HEAD' });
            if (response.status === 401) message = '登录已过期，请返回文件列表重新登录。';
            else if (response.status === 403) message = '当前标签库无权访问此视频。';
            else if (response.status === 404) message = '视频不存在或已移动。';
        } catch { message = '连接中断，点击播放重试或选择下一部。'; }
        if (generation === this.generation) this.showStatus(message);
    }

    togglePlay() {
        if (!this.currentPath()) return;
        if (this.failed) this.playAt(this.currentIndex);
        else if (this.video.paused) this.tryPlay();
        else this.video.pause();
    }

    adjacent(direction) {
        this.playAt(getAdjacentPlaylistIndex(this.playMode, this.playlist.length, this.currentIndex, direction));
    }

    seekBy(seconds) {
        const duration = this.video.duration;
        if (!this.currentPath() || this.failed || !Number.isFinite(duration) || duration <= 0) return;
        this.video.currentTime = Math.min(duration, Math.max(0, this.video.currentTime + seconds));
        this.updateTimeline();
    }

    updateTimeline() {
        const duration = this.video.duration;
        this.el.progress.disabled = this.failed || !Number.isFinite(duration) || duration <= 0;
        this.el.progress.max = Number.isFinite(duration) && duration > 0 ? duration : 1000;
        if (!this.seeking) {
            this.el.progress.value = this.video.currentTime || 0;
            this.updateTime(this.video.currentTime, duration);
            this.fillSlider(this.el.progress);
        }
    }

    updateTime(position, duration = this.video.duration) {
        this.el.time.textContent = `${formatVideoTime(position)} / ${formatVideoTime(duration)}`;
    }
    fillSlider(slider) { slider.style.setProperty('--filled', `${Number(slider.value) / Number(slider.max) * 100}%`); }

    renderPlaylist() {
        this.el.playlist.replaceChildren();
        this.playlist.forEach((path, index) => {
            const row = document.createElement('li');
            row.className = `playlist-row${index === this.currentIndex ? ' current' : ''}`;
            const select = document.createElement('button');
            select.className = 'playlist-select';
            select.title = path;
            if (index === this.currentIndex) select.setAttribute('aria-current', 'true');
            const number = document.createElement('span');
            number.textContent = String(index + 1).padStart(2, '0');
            const name = document.createElement('span');
            name.className = 'name';
            name.textContent = path.split('/').pop();
            select.append(number, name);
            select.addEventListener('click', () => this.playAt(this.playlist.indexOf(path)));
            const remove = document.createElement('button');
            remove.className = 'icon-button remove';
            icon(remove, 'close', `从列表移除 ${name.textContent}`);
            remove.addEventListener('click', () => this.removeAt(this.playlist.indexOf(path)));
            row.append(select, remove);
            this.el.playlist.append(row);
        });
        const counter = `${this.currentIndex + 1} / ${this.playlist.length}`;
        this.el['playlist-title'].textContent = `播放列表（${this.playlist.length}）`;
        this.el['playlist-meta'].textContent = this.playlist.length ? `正在播放 · ${counter}` : '列表为空';
        this.el['video-counter'].textContent = counter;
        this.updateEmpty();
    }

    removeAt(index) {
        if (index < 0) return;
        const removedCurrent = index === this.currentIndex;
        this.playlist.splice(index, 1);
        if (!this.playlist.length) {
            this.generation++;
            this.video.pause();
            this.video.removeAttribute('src');
            this.video.load();
            this.currentIndex = -1;
            this.subtitles.activate(null);
            this.el['video-title'].textContent = '视频播放器';
            this.showStatus('');
            this.updateTime(0, 0);
        } else if (removedCurrent) {
            this.playAt(Math.min(index, this.playlist.length - 1));
        } else if (index < this.currentIndex) this.currentIndex--;
        this.renderPlaylist();
        this.saveContext();
    }

    updateEmpty() {
        const empty = !this.playlist.length;
        this.el['empty-state'].hidden = !empty;
        for (const id of ['play', 'previous', 'next', 'load-subtitle']) this.el[id].disabled = empty;
        this.el['open-original'].hidden = empty;
    }

    setPlaylistVisible(visible) {
        this.el['playlist-sidebar'].hidden = !visible;
        this.el['playlist-toggle'].setAttribute('aria-expanded', String(visible));
        this.showControls();
    }

    openAddDialog() {
        this.closeMenus();
        const available = this.availableFiles.filter(path => !this.playlist.includes(path));
        this.el['available-videos'].replaceChildren();
        for (const path of available) {
            const label = document.createElement('label');
            const input = document.createElement('input');
            input.type = 'checkbox'; input.value = path;
            label.append(input, document.createTextNode(path.split('/').pop()));
            label.title = path;
            this.el['available-videos'].append(label);
        }
        if (!available.length) this.el['available-videos'].textContent = '当前文件列表中的视频均已加入。';
        this.el['confirm-add'].disabled = !available.length;
        this.el['add-dialog'].showModal();
        this.showControls();
    }

    closeMenus() {
        for (const name of ['subtitles', 'more']) {
            this.el[`${name}-menu`].hidden = true;
            this.el[`${name}-button`].setAttribute('aria-expanded', 'false');
        }
    }
    toggleMenu(name) {
        const open = this.el[`${name}-menu`].hidden;
        this.closeMenus();
        this.el[`${name}-menu`].hidden = !open;
        this.el[`${name}-button`].setAttribute('aria-expanded', String(open));
        this.showControls();
    }
    updateSubtitles() {
        this.el['subtitle-status'].textContent = this.subtitles.status;
        this.el['show-subtitles'].checked = this.subtitles.enabled;
        this.el['show-subtitles'].disabled = !this.subtitles.element;
        this.el['subtitles-button'].classList.toggle('active', Boolean(this.subtitles.element && this.subtitles.enabled));
        const text = this.subtitles.text();
        if (this.el.captions.textContent !== text) this.el.captions.textContent = text;
        this.el.captions.hidden = !text;
        this.layoutCaptions();
    }
    layoutCaptions() {
        const stage = this.el['video-stage'];
        const ratio = this.video.videoWidth / this.video.videoHeight;
        const height = Number.isFinite(ratio) && ratio > 0 ? Math.min(stage.clientHeight, stage.clientWidth / ratio) : stage.clientHeight;
        let bottom = (stage.clientHeight - height) / 2 + 12;
        if (document.fullscreenElement === this.root && !this.root.classList.contains('controls-hidden')) {
            bottom = Math.max(bottom, this.el.controls.offsetHeight + 16);
        }
        if (this.el.captions.style.bottom !== `${bottom}px`) this.el.captions.style.bottom = `${bottom}px`;
    }

    async toggleFullscreen() {
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else if (this.root.requestFullscreen) await this.root.requestFullscreen();
            else if (this.video.webkitEnterFullscreen) this.video.webkitEnterFullscreen();
            else this.showStatus('此浏览器不支持全屏播放');
        } catch { this.showStatus('无法进入全屏，请点击全屏按钮重试'); }
    }
    fullscreenChanged() {
        const full = document.fullscreenElement === this.root;
        if (full) {
            this.windowPlaylistVisible = !this.el['playlist-sidebar'].hidden;
            this.setPlaylistVisible(false);
        } else this.setPlaylistVisible(Boolean(this.windowPlaylistVisible));
        icon(this.el.fullscreen, full ? 'restore' : 'fullscreen', full ? '退出全屏 (Esc)' : '全屏 (F)');
        this.showControls();
    }
    showControls() {
        clearTimeout(this.controlsTimer);
        this.root.classList.remove('controls-hidden');
        this.updateSubtitles();
        if (document.fullscreenElement !== this.root || this.video.paused) return;
        this.controlsTimer = setTimeout(() => {
            if (this.draggingControl || this.seeking || this.el.controls.matches(':hover') ||
                this.el['add-dialog'].open || !this.el['subtitles-menu'].hidden || !this.el['more-menu'].hidden ||
                (!this.el['playlist-sidebar'].hidden && this.el['playlist-sidebar'].matches(':hover'))) {
                this.showControls(); return;
            }
            this.root.classList.add('controls-hidden');
            this.updateSubtitles();
        }, 2500);
    }
    keydown(event) {
        if (event.defaultPrevented || event.altKey || event.metaKey || event.shiftKey ||
            this.el['add-dialog'].open || event.target.isContentEditable ||
            event.target.closest('input:not(#progress), textarea, select')) return;
        let handled = true;
        if (event.code === 'Space' && event.target.tagName !== 'BUTTON') this.togglePlay();
        else if (event.ctrlKey && event.key === 'ArrowLeft') this.adjacent(-1);
        else if (event.ctrlKey && event.key === 'ArrowRight') this.adjacent(1);
        else if (!event.ctrlKey && event.key === 'ArrowLeft') this.seekBy(-5);
        else if (!event.ctrlKey && event.key === 'ArrowRight') this.seekBy(5);
        else if (event.ctrlKey && event.key.toLowerCase() === 'l') this.setPlaylistVisible(this.el['playlist-sidebar'].hidden);
        else if (!event.ctrlKey && event.key.toLowerCase() === 'f') this.toggleFullscreen();
        else if (event.key === 'Escape') this.closeMenus();
        else handled = false;
        if (handled) { event.preventDefault(); this.showControls(); }
    }
}

const root = document.getElementById('video-player');
if (root) new WebVideoPlayer(root);
