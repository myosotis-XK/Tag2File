// Native tracks handle cue timing. The page draws text above its custom controls;
// iOS native video fullscreen uses the same track's built-in caption renderer.
export class VideoSubtitles {
    constructor(video, onChange) {
        this.video = video;
        this.onChange = onChange;
        this.enabled = true;
        this.nativeFullscreen = false;
        this.overrides = new Map();
        this.path = null;
        this.version = 0;
        this.status = '未加载字幕';
    }

    clearTrack() {
        if (this.element) {
            this.element.track.mode = 'disabled';
            this.element.remove();
            this.element = null;
        }
        if (this.url) URL.revokeObjectURL(this.url);
        this.url = null;
    }

    activate(path) {
        this.controller?.abort();
        this.version++;
        this.path = path;
        this.clearTrack();
        this.status = path ? '正在查找字幕…' : '未加载字幕';
        this.onChange();
        if (!path) return;
        if (this.overrides.has(path)) this.apply(this.overrides.get(path));
        else this.load();
    }

    async load(file = null) {
        if (!this.path) return;
        if (file && (file.size > 8 * 1024 * 1024 || !/\.srt$/i.test(file.name))) {
            this.status = '请选择不超过 8 MB 的 SRT 文件';
            this.onChange();
            return;
        }
        this.controller?.abort();
        this.controller = new AbortController();
        const version = ++this.version;
        const path = this.path;
        const options = { signal: this.controller.signal };
        let url = `/api/video/subtitles?path=${encodeURIComponent(path)}`;
        if (file) {
            const data = new FormData();
            data.append('path', path);
            data.append('file', file);
            Object.assign(options, { method: 'POST', body: data, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            url = '/api/video/subtitles';
        }
        try {
            const response = await fetch(url, options);
            const data = await response.json();
            if (version !== this.version || path !== this.path) return;
            if (!response.ok) throw new Error(data.message || '字幕加载失败');
            if (!data.exists) {
                this.status = '未找到同名 SRT';
                this.onChange();
                return;
            }
            if (file) {
                this.overrides.set(path, data);
                this.enabled = true;
            }
            this.apply(data);
        } catch (error) {
            if (error.name === 'AbortError' || version !== this.version) return;
            this.status = `${error.message || '字幕加载失败'}${this.element ? '（保留当前字幕）' : ''}`;
            this.onChange();
        }
    }

    apply(data) {
        this.clearTrack();
        this.url = URL.createObjectURL(new Blob([data.content], { type: 'text/vtt' }));
        const element = document.createElement('track');
        element.kind = 'subtitles';
        element.label = data.name;
        element.srclang = 'zh';
        element.src = this.url;
        this.element = element;
        this.video.append(element);
        element.track.mode = this.enabled && this.nativeFullscreen ? 'showing' : 'hidden';
        element.track.addEventListener('cuechange', () => { if (element === this.element) this.onChange(); });
        element.addEventListener('load', () => { if (element === this.element) this.onChange(); });
        element.addEventListener('error', () => {
            if (element !== this.element) return;
            this.clearTrack();
            this.status = '浏览器无法加载字幕';
            this.onChange();
        });
        this.status = data.name + (data.skipped_blocks ? `（跳过 ${data.skipped_blocks} 个无效段落）` : '');
        this.onChange();
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (this.element) this.element.track.mode = enabled && this.nativeFullscreen ? 'showing' : 'hidden';
        this.onChange();
    }

    text() {
        if (!this.enabled || this.nativeFullscreen) return '';
        return [...(this.element?.track.activeCues || [])].map(cue => cue.getCueAsHTML().textContent).join('\n');
    }

    setNativeFullscreen(fullscreen) {
        this.nativeFullscreen = fullscreen;
        this.setEnabled(this.enabled);
    }
}
