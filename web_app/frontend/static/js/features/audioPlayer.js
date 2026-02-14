// audioPlayer.js - 音频播放器核心控制器

import { apiGetAudioMetadata, apiGetLyric, apiOpenFile, apiAddOrUpdateMarker, apiDeleteMarker } from '../api.js';

export class AudioPlayerController {
    constructor() {
        // 音频对象
        this.audio = new Audio();

        // 播放列表
        this.playlist = [];
        this.currentIndex = 0;

        // 播放模式：0=顺序，1=随机，2=单曲循环
        this.playMode = 0;

        // 歌词数据
        this.lyricData = [];
        this.currentLyricIndex = -1;

        // 标记数据
        this.markers = [];

        // 入点/出点（用于创建标记）
        this.inPoint = null;
        this.outPoint = null;

        // DOM 元素
        this.initDOMElements();

        // 事件监听
        this.initEventListeners();

        // 从 URL 参数加载播放列表
        this.loadPlaylistFromURL();
    }

    initDOMElements() {
        // 播放控制
        this.btnPlay = document.getElementById('btn-play');
        this.btnPrevious = document.getElementById('btn-previous');
        this.btnNext = document.getElementById('btn-next');
        this.btnMode = document.getElementById('btn-mode');
        this.btnVolume = document.getElementById('btn-volume');
        this.btnBack = document.getElementById('btn-back');

        // 进度条
        this.progressSlider = document.getElementById('progress-slider');
        this.currentTimeLabel = document.getElementById('current-time');
        this.durationTimeLabel = document.getElementById('duration-time');

        // 音量控制
        this.volumePopup = document.getElementById('volume-popup');
        this.volumeSlider = document.getElementById('volume-slider');
        this.volumeValue = document.getElementById('volume-value');

        // 显示区域：封面/歌词切换
        this.displayArea = document.getElementById('display-area');
        this.coverView = document.getElementById('cover-view');
        this.lyricView = document.getElementById('lyric-view');
        this.coverImage = document.getElementById('cover-image');
        this.trackTitle = document.getElementById('track-title');
        this.trackArtist = document.getElementById('track-artist');

        // 侧边栏
        this.sidebar = document.getElementById('sidebar');
        this.sidebarOverlay = document.getElementById('sidebar-overlay');
        this.btnSidebarToggle = document.getElementById('btn-sidebar-toggle');
        this.btnSidebarClose = document.getElementById('btn-sidebar-close');
        this.sidebarTabButtons = document.querySelectorAll('.sidebar-tab-btn');
        this.sidebarPanes = document.querySelectorAll('.sidebar-pane');

        // 内容容器
        this.lyricContainer = document.getElementById('lyric-container');
        this.markerList = document.getElementById('marker-list');
        this.playlistContainer = document.getElementById('playlist-container');

        // 标记快速创建
        this.btnMarkIn = document.getElementById('btn-mark-in');
        this.btnMarkOut = document.getElementById('btn-mark-out');
        this.inputInPoint = document.getElementById('input-in-point');
        this.inputOutPoint = document.getElementById('input-out-point');
        this.inputMarkerLabel = document.getElementById('input-marker-label');
        this.inputMarkerColor = document.getElementById('input-marker-color');
        this.btnCreateMarker = document.getElementById('btn-create-marker');
        this.btnClearMarker = document.getElementById('btn-clear-marker');

        // 视图状态
        this.isShowingLyric = false;
    }

    initEventListeners() {
        // 音频事件
        this.audio.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('ended', () => this.onEnded());
        this.audio.addEventListener('play', () => this.updatePlayButton(true));
        this.audio.addEventListener('pause', () => this.updatePlayButton(false));

        // 播放控制按钮
        this.btnPlay.addEventListener('click', () => this.togglePlay());
        this.btnPrevious.addEventListener('click', () => this.playPrevious());
        this.btnNext.addEventListener('click', () => this.playNext());
        this.btnMode.addEventListener('click', () => this.togglePlayMode());
        this.btnVolume.addEventListener('click', () => this.toggleVolumePopup());
        this.btnBack.addEventListener('click', () => this.goBack());

        // 进度条
        this.progressSlider.addEventListener('input', (e) => this.onProgressChange(e));

        // 音量控制
        this.volumeSlider.addEventListener('input', (e) => this.onVolumeChange(e));

        // 封面/歌词切换
        this.displayArea.addEventListener('click', () => this.toggleDisplayView());

        // 侧边栏控制
        this.btnSidebarToggle.addEventListener('click', () => this.openSidebar());
        this.btnSidebarClose.addEventListener('click', () => this.closeSidebar());
        this.sidebarOverlay.addEventListener('click', () => this.closeSidebar());

        // 侧边栏标签页切换
        this.sidebarTabButtons.forEach(btn => {
            btn.addEventListener('click', () => this.switchSidebarTab(btn.dataset.tab));
        });

        // 标记快速创建
        this.btnMarkIn.addEventListener('click', () => this.markInPoint());
        this.btnMarkOut.addEventListener('click', () => this.markOutPoint());
        this.btnCreateMarker.addEventListener('click', () => this.createMarker());
        this.btnClearMarker.addEventListener('click', () => this.clearMarkerInputs());

        // 点击外部关闭音量弹窗
        document.addEventListener('click', (e) => {
            if (!this.btnVolume.contains(e.target) && !this.volumePopup.contains(e.target)) {
                this.volumePopup.style.display = 'none';
            }
        });

        // 初始化音量
        this.audio.volume = 0.5;
    }

    async loadPlaylistFromURL() {
        const params = new URLSearchParams(window.location.search);
        const playlistParam = params.get('playlist');
        const indexParam = params.get('index');

        if (!playlistParam) {
            this.trackTitle.textContent = '未找到播放列表';
            return;
        }

        try {
            this.playlist = JSON.parse(decodeURIComponent(playlistParam));
            this.currentIndex = indexParam ? parseInt(indexParam) : 0;

            // 加载元数据
            await this.loadMetadata();

            // 渲染播放列表
            this.renderPlaylist();

            // 加载并播放当前歌曲
            await this.loadCurrentSong();
        } catch (error) {
            console.error('加载播放列表失败:', error);
            this.trackTitle.textContent = '加载失败';
        }
    }

    async loadMetadata() {
        try {
            const response = await apiGetAudioMetadata(this.playlist);
            this.playlistMetadata = response.metadata;
        } catch (error) {
            console.error('加载元数据失败:', error);
            this.playlistMetadata = [];
        }
    }

    async loadCurrentSong() {
        if (this.playlist.length === 0) return;

        const filePath = this.playlist[this.currentIndex];
        const metadata = this.playlistMetadata?.[this.currentIndex];

        // 更新歌曲信息
        this.trackTitle.textContent = metadata?.title || '未知歌曲';
        this.trackArtist.textContent = metadata?.artist || '未知艺术家';

        // 加载封面（使用缩略图 API）
        this.coverImage.src = `/get_thumb?path=${encodeURIComponent(filePath)}&size=250`;

        // 加载音频
        this.audio.src = apiOpenFile(filePath);

        // 加载歌词
        if (metadata?.has_lyric) {
            await this.loadLyric(filePath);
        } else {
            this.lyricData = [];
            this.renderLyric();
        }

        // 加载标记
        this.markers = metadata?.markers || [];
        this.renderMarkers();

        // 更新播放列表高亮
        this.updatePlaylistHighlight();

        // 开始播放
        try {
            await this.audio.play();
        } catch (error) {
            console.log('自动播放被阻止，需要用户交互');
        }
    }

    async loadLyric(filePath) {
        try {
            const response = await apiGetLyric(filePath);
            if (response.exists) {
                this.lyricData = this.parseLyric(response.content);
                this.renderLyric();
            }
        } catch (error) {
            console.error('加载歌词失败:', error);
        }
    }

    parseLyric(lrcContent) {
        const lines = lrcContent.split('\n');
        const parsed = [];

        lines.forEach(line => {
            // 匹配 [mm:ss.xx]歌词文本 格式
            const match = line.match(/\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)/);
            if (match) {
                const minutes = parseInt(match[1]);
                const seconds = parseInt(match[2]);
                const milliseconds = parseInt(match[3]);
                const time = minutes * 60 + seconds + milliseconds / 100;
                const text = match[4].trim();

                if (text) {
                    parsed.push({ time, text });
                }
            }
        });

        return parsed.sort((a, b) => a.time - b.time);
    }

    renderLyric() {
        if (this.lyricData.length === 0) {
            this.lyricContainer.innerHTML = '<p class="text-muted text-center">暂无歌词</p>';
            return;
        }

        this.lyricContainer.innerHTML = this.lyricData.map((line, index) =>
            `<div class="lyric-line" data-lyric-index="${index}" data-time="${line.time}">
                ${line.text}
            </div>`
        ).join('');

        // 添加点击事件
        this.lyricContainer.querySelectorAll('.lyric-line').forEach(el => {
            el.addEventListener('click', () => {
                const time = parseFloat(el.dataset.time);
                this.audio.currentTime = time;
            });
        });
    }

    renderMarkers() {
        if (this.markers.length === 0) {
            this.markerList.innerHTML = '<p class="text-muted text-center">暂无标记</p>';
            return;
        }

        this.markerList.innerHTML = this.markers.map(marker => {
            const time = marker.type === 0
                ? this.formatTime(marker.time)
                : `${this.formatTime(marker.start)} - ${this.formatTime(marker.end)}`;

            return `
                <div class="marker-item" data-marker-id="${marker.id}" data-time="${marker.time || marker.start}">
                    <div class="marker-color" style="background: ${marker.color}"></div>
                    <div class="marker-info">
                        <div class="marker-time">${time}</div>
                        <div class="marker-label">${marker.label}</div>
                    </div>
                    <div class="marker-actions">
                        <button class="btn btn-sm btn-outline-light btn-edit-marker" title="编辑">
                            <i class="fa fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger btn-delete-marker" title="删除">
                            <i class="fa fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // 添加点击跳转事件
        this.markerList.querySelectorAll('.marker-item').forEach(el => {
            const markerId = parseInt(el.dataset.markerId);
            const marker = this.markers.find(m => m.id === markerId);

            // 点击标记主体区域跳转
            const markerInfo = el.querySelector('.marker-info');
            markerInfo.addEventListener('click', () => {
                const time = parseFloat(el.dataset.time);
                this.audio.currentTime = time / 1000;
            });

            // 编辑按钮
            const btnEdit = el.querySelector('.btn-edit-marker');
            btnEdit.addEventListener('click', (e) => {
                e.stopPropagation();
                this.editMarker(marker);
            });

            // 删除按钮
            const btnDelete = el.querySelector('.btn-delete-marker');
            btnDelete.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteMarker(marker);
            });
        });
    }

    renderPlaylist() {
        if (this.playlist.length === 0) {
            this.playlistContainer.innerHTML = '<p class="text-muted text-center">播放列表为空</p>';
            return;
        }

        this.playlistContainer.innerHTML = this.playlist.map((filePath, index) => {
            const metadata = this.playlistMetadata?.[index];
            const title = metadata?.title || filePath.split('/').pop();
            const isPlaying = index === this.currentIndex;

            return `
                <div class="playlist-item ${isPlaying ? 'playing' : ''}" data-index="${index}">
                    <span class="playlist-index">${index + 1}</span>
                    <span class="playlist-title">${title}</span>
                </div>
            `;
        }).join('');

        // 添加点击事件
        this.playlistContainer.querySelectorAll('.playlist-item').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.dataset.index);
                this.playAtIndex(index);
            });
        });
    }

    updatePlaylistHighlight() {
        const items = this.playlistContainer.querySelectorAll('.playlist-item');
        items.forEach((item, index) => {
            if (index === this.currentIndex) {
                item.classList.add('playing');
            } else {
                item.classList.remove('playing');
            }
        });
    }

    // ========== 播放控制 ==========

    togglePlay() {
        if (this.audio.paused) {
            this.audio.play();
        } else {
            this.audio.pause();
        }
    }

    updatePlayButton(isPlaying) {
        const icon = this.btnPlay.querySelector('i');
        if (isPlaying) {
            icon.className = 'fa fa-pause';
            this.btnPlay.title = '暂停';
        } else {
            icon.className = 'fa fa-play';
            this.btnPlay.title = '播放';
        }
    }

    async playPrevious() {
        if (this.playMode === 1) {
            // 随机模式
            this.currentIndex = Math.floor(Math.random() * this.playlist.length);
        } else {
            this.currentIndex = (this.currentIndex - 1 + this.playlist.length) % this.playlist.length;
        }
        await this.loadCurrentSong();
    }

    async playNext() {
        if (this.playMode === 1) {
            // 随机模式
            const candidates = [...Array(this.playlist.length).keys()]
                .filter(i => i !== this.currentIndex);
            this.currentIndex = candidates[Math.floor(Math.random() * candidates.length)];
        } else {
            this.currentIndex = (this.currentIndex + 1) % this.playlist.length;
        }
        await this.loadCurrentSong();
    }

    async playAtIndex(index) {
        this.currentIndex = index;
        await this.loadCurrentSong();
    }

    togglePlayMode() {
        this.playMode = (this.playMode + 1) % 3;
        const icon = this.btnMode.querySelector('i');

        if (this.playMode === 0) {
            icon.className = 'fa fa-retweet';
            this.btnMode.title = '顺序播放';
        } else if (this.playMode === 1) {
            icon.className = 'fa fa-random';
            this.btnMode.title = '随机播放';
        } else {
            icon.className = 'fa fa-repeat';
            this.btnMode.title = '单曲循环';
        }
    }

    onEnded() {
        if (this.playMode === 2) {
            // 单曲循环
            this.audio.currentTime = 0;
            this.audio.play();
        } else {
            this.playNext();
        }
    }

    // ========== 进度和时间 ==========

    onLoadedMetadata() {
        this.progressSlider.max = this.audio.duration;
        this.durationTimeLabel.textContent = this.formatTime(this.audio.duration * 1000);
    }

    onTimeUpdate() {
        // 更新进度条
        this.progressSlider.value = this.audio.currentTime;
        this.currentTimeLabel.textContent = this.formatTime(this.audio.currentTime * 1000);

        // 更新歌词
        this.updateLyricHighlight();
    }

    onProgressChange(e) {
        this.audio.currentTime = e.target.value;
    }

    updateLyricHighlight() {
        if (this.lyricData.length === 0) return;

        const currentTime = this.audio.currentTime;
        let newIndex = -1;

        for (let i = 0; i < this.lyricData.length; i++) {
            if (i === this.lyricData.length - 1 ||
                currentTime < this.lyricData[i + 1].time) {
                newIndex = i;
                break;
            }
        }

        if (newIndex !== this.currentLyricIndex) {
            this.currentLyricIndex = newIndex;

            // 更新高亮
            const lines = this.lyricContainer.querySelectorAll('.lyric-line');
            lines.forEach((line, index) => {
                if (index === newIndex) {
                    line.classList.add('active');
                    line.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                    line.classList.remove('active');
                }
            });
        }
    }

    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor((seconds / 1000) / 60);
        const secs = Math.floor((seconds / 1000) % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // ========== 音量控制 ==========

    toggleVolumePopup() {
        const isHidden = this.volumePopup.style.display === 'none';
        this.volumePopup.style.display = isHidden ? 'flex' : 'none';
    }

    onVolumeChange(e) {
        const volume = e.target.value / 100;
        this.audio.volume = volume;
        this.volumeValue.textContent = `${e.target.value}%`;

        // 更新音量图标
        const icon = this.btnVolume.querySelector('i');
        if (volume === 0) {
            icon.className = 'fa fa-volume-off';
        } else if (volume < 0.5) {
            icon.className = 'fa fa-volume-down';
        } else {
            icon.className = 'fa fa-volume-up';
        }
    }

    // ========== 显示视图切换 ==========

    toggleDisplayView() {
        this.isShowingLyric = !this.isShowingLyric;

        if (this.isShowingLyric) {
            // 显示歌词视图
            this.coverView.style.opacity = '0';
            this.coverView.style.transform = 'scale(0.9)';
            this.lyricView.style.display = 'flex';
            setTimeout(() => {
                this.lyricView.style.opacity = '1';
                this.lyricView.style.transform = 'scale(1)';
            }, 50);
        } else {
            // 显示封面视图
            this.lyricView.style.opacity = '0';
            this.lyricView.style.transform = 'scale(0.9)';
            setTimeout(() => {
                this.lyricView.style.display = 'none';
                this.coverView.style.opacity = '1';
                this.coverView.style.transform = 'scale(1)';
            }, 300);
        }
    }

    // ========== 侧边栏控制 ==========

    openSidebar() {
        this.sidebar.classList.add('active');
        this.sidebarOverlay.classList.add('active');
    }

    closeSidebar() {
        this.sidebar.classList.remove('active');
        this.sidebarOverlay.classList.remove('active');
    }

    switchSidebarTab(tabName) {
        // 切换标签按钮状态
        this.sidebarTabButtons.forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 切换面板显示
        this.sidebarPanes.forEach(pane => {
            if (pane.id === `sidebar-${tabName}`) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
    }

    // ========== 标记功能 ==========

    markInPoint() {
        this.inPoint = this.audio.currentTime;
        this.inputInPoint.value = this.formatTime(this.inPoint * 1000);
    }

    markOutPoint() {
        this.outPoint = this.audio.currentTime;
        this.inputOutPoint.value = this.formatTime(this.outPoint * 1000);
    }

    clearMarkerInputs() {
        this.inPoint = null;
        this.outPoint = null;
        this.inputInPoint.value = '';
        this.inputOutPoint.value = '';
        this.inputMarkerLabel.value = '';
        this.inputMarkerColor.value = '#ff0000';
        this.btnCreateMarker.innerHTML = '<i class="fa fa-plus"></i> 创建';
        delete this.btnCreateMarker.dataset.editingMarkerId;
    }

    async createMarker() {
        const label = this.inputMarkerLabel.value.trim();
        if (!label) {
            alert('请输入标记名称');
            return;
        }

        const color = this.inputMarkerColor.value;
        const filePath = this.playlist[this.currentIndex];

        // 创建标记数据
        const markerData = {
            id: null,  // null 表示新建
            type: this.inPoint !== null && this.outPoint !== null ? 1 : 0,
            label: label,
            color: color,
            time: this.inPoint * 1000 || this.audio.currentTime * 1000,
            start: this.inPoint * 1000,
            end: this.outPoint * 1000
        };

        try {
            // 调用后端 API 保存标记
            const response = await apiAddOrUpdateMarker(filePath, markerData);

            if (response.success) {
                // 更新本地标记列表
                this.markers = response.markers;
                this.renderMarkers();

                // 清空输入
                this.inputMarkerLabel.value = '';
                this.inPoint = null;
                this.outPoint = null;
                this.inputInPoint.value = '';
                this.inputOutPoint.value = '';

                console.log('标记创建成功:', markerData);
            } else {
                alert('创建标记失败: ' + (response.error || '未知错误'));
            }
        } catch (error) {
            console.error('创建标记失败:', error);
            alert('创建标记失败，请检查网络连接');
        }
    }

    async editMarker(marker) {
        // 填充入点/出点输入框
        if (marker.type === 1) {
            this.inPoint = marker.start;
            this.outPoint = marker.end;
            this.inputInPoint.value = this.formatTime(marker.start);
            this.inputOutPoint.value = this.formatTime(marker.end);
        } else {
            this.inPoint = marker.time;
            this.outPoint = null;
            this.inputInPoint.value = this.formatTime(marker.time);
            this.inputOutPoint.value = '';
        }

        // 填充标签和颜色
        this.inputMarkerLabel.value = marker.label;
        this.inputMarkerColor.value = marker.color;

        // 切换到标记面板
        this.switchTab('marker');

        // 提示用户
        alert('标记已加载到编辑面板，修改后点击"创建"按钮更新');

        // 修改创建按钮为更新模式
        this.btnCreateMarker.innerHTML = '<i class="fa fa-save"></i> 更新';
        this.btnCreateMarker.dataset.editingMarkerId = marker.id;
    }

    async deleteMarker(marker) {
        if (!confirm(`确定要删除标记 "${marker.label}" 吗？`)) {
            return;
        }

        const filePath = this.playlist[this.currentIndex];

        try {
            const response = await apiDeleteMarker(filePath, marker.id);

            if (response.success) {
                // 更新本地标记列表
                this.markers = response.markers;
                this.renderMarkers();

                console.log('标记删除成功:', marker);
            } else {
                alert('删除标记失败: ' + (response.error || '未知错误'));
            }
        } catch (error) {
            console.error('删除标记失败:', error);
            alert('删除标记失败，请检查网络连接');
        }
    }

    // ========== 其他 ==========

    goBack() {
        window.history.back();
    }
}
