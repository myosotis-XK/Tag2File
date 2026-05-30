import {
  apiAddOrUpdateMarker,
  apiDeleteMarker,
  apiGetAudioMetadata,
  apiGetLyric,
  apiGetMarkerPresets,
  apiOpenFile,
} from '../api.js';
import {
  getAdjacentPlaylistIndex,
  loadAudioPlayerContext,
  loadLegacyAudioPlayerContext,
  saveAudioPlayerContext,
  updateAudioPlayerIndex,
} from './audioPlayerContext.js';
import {
  findCenteredLyricLine,
  parseLyricContent,
  renderLyricLines,
  updateLyricActiveLine,
} from './audioPlayerLyrics.js';
import {
  buildMarkerPayload,
  populateMarkerForm,
  renderMarkerItems,
  renderPresetItems,
  resetMarkerForm,
} from './audioPlayerMarkers.js';
import {
  renderPlaylistItems,
  updatePlaylistPlayingState,
} from './audioPlayerPlaylist.js';

const LYRIC_TOUCH_DRAG_THRESHOLD = 8;
const LYRIC_MOUSE_DRAG_THRESHOLD = 18;
const LYRIC_PREVIEW_IDLE_TIMEOUT = 3000;
const LYRIC_CLICK_SUPPRESS_MS = 700;
const LYRIC_AUTO_SCROLL_IGNORE_MS = 500;

export class AudioPlayerController {
  constructor() {
    this.audio = new Audio();
    this.playlist = [];
    this.playlistMetadata = [];
    this.currentIndex = 0;
    this.playMode = 0;
    this.lyricData = [];
    this.currentLyricIndex = -1;
    this.markers = [];
    this.markerPresets = [];
    this.inPoint = null;
    this.outPoint = null;
    this.isShowingLyric = false;
    this.lyricInteraction = {
      isPreviewing: false,
      pointerActive: false,
      pointerId: null,
      pointerType: '',
      startScrollTop: 0,
      startY: 0,
      previewIndex: -1,
      exitTimer: null,
      autoScrollIgnoreUntil: 0,
      suppressDisplayToggleUntil: 0,
    };

    this.initDOMElements();
    this.cacheInitialUIState();
    this.initEventListeners();
    this.restoreInitialVolume();
    this.loadInitialContext();
    this.loadMarkerPresets();
  }

  initDOMElements() {
    this.btnPlay = document.getElementById('btn-play');
    this.btnRewind = document.getElementById('btn-rewind');
    this.btnForward = document.getElementById('btn-forward');
    this.btnMode = document.getElementById('btn-mode');
    this.btnVolume = document.getElementById('btn-volume');
    this.btnBack = document.getElementById('btn-back');

    this.progressSlider = document.getElementById('progress-slider');
    this.currentTimeLabel = document.getElementById('current-time');
    this.durationTimeLabel = document.getElementById('duration-time');

    this.volumePopup = document.getElementById('volume-popup');
    this.volumeSlider = document.getElementById('volume-slider');
    this.volumeValue = document.getElementById('volume-value');

    this.displayArea = document.getElementById('display-area');
    this.coverView = document.getElementById('cover-view');
    this.lyricView = document.getElementById('lyric-view');
    this.coverImage = document.getElementById('cover-image');
    this.trackTitle = document.getElementById('track-title');
    this.trackArtist = document.getElementById('track-artist');

    this.sidebar = document.getElementById('sidebar');
    this.sidebarOverlay = document.getElementById('sidebar-overlay');
    this.btnSidebarToggle = document.getElementById('btn-sidebar-toggle');
    this.btnSidebarClose = document.getElementById('btn-sidebar-close');
    this.sidebarTabButtons = document.querySelectorAll('.sidebar-tab-btn');
    this.sidebarPanes = document.querySelectorAll('.sidebar-pane');

    this.lyricContainer = document.getElementById('lyric-container');
    this.markerList = document.getElementById('marker-list');
    this.playlistContainer = document.getElementById('playlist-container');

    this.btnMarkIn = document.getElementById('btn-mark-in');
    this.btnMarkOut = document.getElementById('btn-mark-out');
    this.inputInPoint = document.getElementById('input-in-point');
    this.inputOutPoint = document.getElementById('input-out-point');
    this.inputMarkerLabel = document.getElementById('input-marker-label');
    this.btnSelectPreset = document.getElementById('btn-select-preset');
    this.inputMarkerColor = document.getElementById('input-marker-color');
    this.btnCreateMarker = document.getElementById('btn-create-marker');
    this.btnClearMarker = document.getElementById('btn-clear-marker');

    this.presetPopupOverlay = document.getElementById('preset-popup-overlay');
    this.presetPopup = document.getElementById('preset-popup');
    this.btnClosePreset = document.getElementById('btn-close-preset');
    this.presetGrid = document.getElementById('preset-grid');
  }

  cacheInitialUIState() {
    this.defaultLyricHTML = this.lyricContainer.innerHTML;
    this.defaultMarkerHTML = this.markerList.innerHTML;
    this.defaultPlaylistHTML = this.playlistContainer.innerHTML;
    this.defaultCreateMarkerHTML = this.btnCreateMarker.innerHTML;
  }

  initEventListeners() {
    this.audio.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
    this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
    this.audio.addEventListener('ended', () => this.onEnded());
    this.audio.addEventListener('play', () => this.updatePlayButton(true));
    this.audio.addEventListener('pause', () => this.updatePlayButton(false));

    this.btnPlay.addEventListener('click', () => this.togglePlay());
    this.btnRewind.addEventListener('click', () => this.rewindSeconds());
    this.btnForward.addEventListener('click', () => this.forwardSeconds());
    this.btnMode.addEventListener('click', () => this.togglePlayMode());
    this.btnVolume.addEventListener('click', () => this.toggleVolumePopup());
    this.btnBack.addEventListener('click', () => this.goBack());

    this.progressSlider.addEventListener('input', event => this.onProgressChange(event));
    this.volumeSlider.addEventListener('input', event => this.onVolumeChange(event));
    this.displayArea.addEventListener('click', event => this.onDisplayAreaClick(event));
    this.lyricContainer.addEventListener('pointerdown', event => this.onLyricPointerDown(event));
    this.lyricContainer.addEventListener('pointermove', event => this.onLyricPointerMove(event));
    this.lyricContainer.addEventListener('pointerup', event => this.onLyricPointerUp(event));
    this.lyricContainer.addEventListener('pointercancel', event => this.onLyricPointerUp(event));
    this.lyricContainer.addEventListener('click', event => this.onLyricContainerClick(event), true);
    this.lyricContainer.addEventListener('pointerleave', event => {
      if (event.buttons) {
        this.onLyricPointerUp(event);
      }
    });
    this.lyricContainer.addEventListener('scroll', () => this.onLyricScroll(), { passive: true });

    this.btnSidebarToggle.addEventListener('click', () => this.openSidebar());
    this.btnSidebarClose.addEventListener('click', () => this.closeSidebar());
    this.sidebarOverlay.addEventListener('click', () => this.closeSidebar());

    this.sidebarTabButtons.forEach(button => {
      button.addEventListener('click', () => this.switchSidebarTab(button.dataset.tab));
    });

    this.btnMarkIn.addEventListener('click', () => this.markInPoint());
    this.btnMarkOut.addEventListener('click', () => this.markOutPoint());
    this.btnSelectPreset.addEventListener('click', () => this.openPresetPopup());
    this.btnClosePreset.addEventListener('click', () => this.closePresetPopup());
    this.presetPopupOverlay.addEventListener('click', () => this.closePresetPopup());
    this.btnCreateMarker.addEventListener('click', () => this.createMarker());
    this.btnClearMarker.addEventListener('click', () => this.clearMarkerInputs());

    document.addEventListener('click', event => {
      if (!this.btnVolume.contains(event.target) && !this.volumePopup.contains(event.target)) {
        this.volumePopup.style.display = 'none';
      }
    });

    document.addEventListener('keydown', event => this.handleKeyboardShortcuts(event));
  }

  restoreInitialVolume() {
    this.audio.volume = 0.5;
    this.volumeSlider.value = '50';
    this.volumeValue.textContent = '50%';
  }

  async loadInitialContext() {
    const storedContext = loadAudioPlayerContext();
    if (storedContext) {
      await this.applyPlaylistContext(storedContext);
      return;
    }

    const legacyContext = loadLegacyAudioPlayerContext();
    if (legacyContext) {
      saveAudioPlayerContext(legacyContext);
        window.history.replaceState({}, '', '/audio/player');
      await this.applyPlaylistContext(legacyContext);
      return;
    }

    this.trackTitle.textContent = '未找到播放列表';
  }

  async applyPlaylistContext(context) {
    this.playlist = context.playlist;
    this.currentIndex = context.currentIndex;
    await this.loadMetadata();
    this.renderPlaylist();
    await this.loadCurrentSong();
  }

  getCurrentFilePath() {
    return this.playlist[this.currentIndex] || null;
  }

  getCurrentMetadata() {
    return this.playlistMetadata?.[this.currentIndex] || null;
  }

  saveCurrentPlaybackContext() {
    if (this.playlist.length > 0) {
      updateAudioPlayerIndex(this.currentIndex);
    }
  }

  handleKeyboardShortcuts(event) {
    if (!(event.ctrlKey && event.shiftKey && event.altKey)) {
      return;
    }

    event.preventDefault();
    switch (event.key) {
      case 'ArrowLeft':
        this.rewindSeconds();
        break;
      case 'ArrowRight':
        this.forwardSeconds();
        break;
      case 'i':
      case 'I':
        this.markInPoint();
        break;
      case 'o':
      case 'O':
        this.markOutPoint();
        break;
      case 'p':
      case 'P':
        this.createPointMarker();
        break;
      case 'r':
      case 'R':
        this.createRangeMarker();
        break;
      default:
        break;
    }
  }

  playShortcutErrorSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      oscillator.frequency.value = 800;
      oscillator.type = 'square';
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.1);
      setTimeout(() => audioContext.close(), 200);
    } catch (error) {
      console.warn('无法播放快捷键错误提示音:', error);
    }
  }

  async createPointMarker() {
    await this.createQuickPointMarker(this.audio.currentTime);
  }

  async createRangeMarker() {
    if (this.inPoint === null || this.outPoint === null || this.inPoint >= this.outPoint) {
      this.playShortcutErrorSound();
      return;
    }

    await this.createQuickRangeMarker(this.inPoint, this.outPoint);
  }

  async createQuickPointMarker(timePoint) {
    await this.saveQuickMarker({
      id: null,
      type: 0,
      label: '快速标记',
      color: '#000000',
      time: this.secondsToMilliseconds(timePoint),
      start: 0,
      end: 0,
    });
  }

  async createQuickRangeMarker(startTime, endTime) {
    await this.saveQuickMarker({
      id: null,
      type: 1,
      label: '快速标记',
      color: '#000000',
      time: this.secondsToMilliseconds(startTime),
      start: this.secondsToMilliseconds(startTime),
      end: this.secondsToMilliseconds(endTime),
    });
    this.clearMarkerInputs();
  }

  async saveQuickMarker(markerData) {
    try {
      const result = await apiAddOrUpdateMarker(this.getCurrentFilePath(), markerData);
      if (result.success) {
        this.markers = result.markers;
        this.renderMarkers();
      }
    } catch (error) {
      console.error('创建标记失败:', error);
      this.playShortcutErrorSound();
    }
  }

  async loadMetadata() {
    try {
      const response = await apiGetAudioMetadata(this.playlist);
      this.playlistMetadata = response.metadata || [];
    } catch (error) {
      console.error('加载音频元数据失败:', error);
      this.playlistMetadata = [];
    }
  }

  async loadMarkerPresets() {
    try {
      const response = await apiGetMarkerPresets();
      if (response.success) {
        this.markerPresets = response.presets;
      }
    } catch (error) {
      console.error('加载标记预设失败:', error);
      this.markerPresets = [
        { id: 1, name: '重要', color: '#e74c3c', order_index: 0 },
        { id: 2, name: '一般', color: '#3498db', order_index: 1 },
        { id: 3, name: '参考', color: '#2ecc71', order_index: 2 },
      ];
    }
  }

  openPresetPopup() {
    this.renderPresetGrid();
    this.presetPopupOverlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  closePresetPopup() {
    this.presetPopupOverlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  renderPresetGrid() {
    renderPresetItems({
      markerPresets: this.markerPresets,
      presetGrid: this.presetGrid,
      emptyHTML: '<p class="text-muted text-center">暂无预设</p>',
      onSelect: preset => {
        this.inputMarkerLabel.value = preset.name;
        this.inputMarkerColor.value = preset.color;
        this.closePresetPopup();
      },
    });
  }

  async loadCurrentSong() {
    if (this.playlist.length === 0) {
      return;
    }

    const filePath = this.getCurrentFilePath();
    const metadata = this.getCurrentMetadata();

    this.trackTitle.textContent = metadata?.title || '未知歌曲';
    this.trackArtist.textContent = metadata?.artist || '未知艺术家';
    this.coverImage.src = `/get_thumb?path=${encodeURIComponent(filePath)}&size=250`;
    this.audio.src = apiOpenFile(filePath);

    if (metadata?.has_lyric) {
      await this.loadLyric(filePath);
    } else {
      this.lyricData = [];
      this.renderLyric();
    }

    this.markers = Array.isArray(metadata?.markers) ? metadata.markers : [];
    this.renderMarkers();
    this.updatePlaylistHighlight();
    this.saveCurrentPlaybackContext();

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
      } else {
        this.lyricData = [];
      }
      this.renderLyric();
    } catch (error) {
      console.error('加载歌词失败:', error);
      this.lyricData = [];
      this.renderLyric();
    }
  }

  parseLyric(lrcContent) {
    return parseLyricContent(lrcContent);
  }

  renderLyric() {
    this.currentLyricIndex = -1;
    this.resetLyricInteraction();
    renderLyricLines({
      lyricData: this.lyricData,
      lyricContainer: this.lyricContainer,
      emptyHTML: this.defaultLyricHTML,
    });
  }

  renderMarkers() {
    renderMarkerItems({
      markers: this.markers,
      markerList: this.markerList,
      emptyHTML: this.defaultMarkerHTML,
      formatTime: value => this.formatTime(value),
      onSeek: time => {
        this.audio.currentTime = time / 1000;
      },
      onEdit: marker => this.editMarker(marker),
      onDelete: marker => this.deleteMarker(marker),
    });
  }

  renderPlaylist() {
    renderPlaylistItems({
      playlist: this.playlist,
      playlistMetadata: this.playlistMetadata,
      playlistContainer: this.playlistContainer,
      emptyHTML: this.defaultPlaylistHTML,
      currentIndex: this.currentIndex,
      onSelect: index => this.playAtIndex(index),
    });
  }

  updatePlaylistHighlight() {
    updatePlaylistPlayingState({
      playlistContainer: this.playlistContainer,
      currentIndex: this.currentIndex,
    });
  }

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
    if (this.playlist.length === 0) {
      return;
    }
    this.currentIndex = getAdjacentPlaylistIndex(this.playMode, this.playlist.length, this.currentIndex, -1);
    await this.loadCurrentSong();
  }

  async playNext() {
    if (this.playlist.length === 0) {
      return;
    }
    this.currentIndex = getAdjacentPlaylistIndex(this.playMode, this.playlist.length, this.currentIndex, 1);
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
      this.audio.currentTime = 0;
      this.audio.play();
      return;
    }
    this.playNext();
  }

  onLoadedMetadata() {
    this.progressSlider.max = this.audio.duration;
    this.durationTimeLabel.textContent = this.formatTime(this.audio.duration * 1000);
  }

  onTimeUpdate() {
    this.progressSlider.value = this.audio.currentTime;
    this.currentTimeLabel.textContent = this.formatTime(this.audio.currentTime * 1000);
    this.updateLyricHighlight();
  }

  onProgressChange(event) {
    this.audio.currentTime = Number.parseFloat(event.target.value);
  }

  updateLyricHighlight() {
    const shouldAutoScroll = !this.lyricInteraction.isPreviewing;
    if (shouldAutoScroll) {
      this.lyricInteraction.autoScrollIgnoreUntil = Date.now() + LYRIC_AUTO_SCROLL_IGNORE_MS;
    }

    this.currentLyricIndex = updateLyricActiveLine({
      lyricData: this.lyricData,
      lyricContainer: this.lyricContainer,
      currentTime: this.audio.currentTime,
      currentLyricIndex: this.currentLyricIndex,
      shouldAutoScroll,
    });
  }

  onLyricPointerDown(event) {
    if (!this.canHandleLyricGesture()) {
      return;
    }

    Object.assign(this.lyricInteraction, {
      pointerActive: true,
      pointerId: event.pointerId,
      pointerType: event.pointerType,
      startScrollTop: this.lyricContainer.scrollTop,
      startY: event.clientY,
    });
    this.lyricContainer.setPointerCapture?.(event.pointerId);
  }

  onLyricPointerMove(event) {
    if (!this.canHandleLyricGesture() || !this.isActiveLyricPointer(event)) {
      return;
    }

    if (this.lyricInteraction.pointerType === 'mouse' && (event.buttons & 1) === 0) {
      this.onLyricPointerUp(event);
      return;
    }

    const offsetY = event.clientY - this.lyricInteraction.startY;
    if (!this.lyricInteraction.isPreviewing) {
      const dragThreshold = this.getLyricDragThreshold();
      if (Math.abs(offsetY) < dragThreshold) {
        return;
      }
      this.enterLyricPreview();
      this.suppressDisplayToggle();
    }

    event.preventDefault();
    this.lyricContainer.scrollTop = this.lyricInteraction.startScrollTop - offsetY;
    this.updateLyricPreviewLine();
  }

  onLyricPointerUp(event) {
    if (!this.lyricInteraction.pointerActive) {
      return;
    }

    const selectedLine = this.getPreviewLineAtPoint(event.clientX, event.clientY);

    const pointerId = event?.pointerId ?? this.lyricInteraction.pointerId;
    if (pointerId !== null && pointerId !== undefined) {
      this.lyricContainer.releasePointerCapture?.(pointerId);
    }

    this.clearLyricPointerState();

    if (selectedLine) {
      event.preventDefault();
      this.seekToLyricLine(selectedLine);
      return;
    }

    if (this.lyricInteraction.isPreviewing) {
      this.scheduleLyricPreviewExit();
    }
  }

  enterLyricPreview() {
    this.lyricInteraction.isPreviewing = true;
    this.lyricInteraction.startScrollTop = this.lyricContainer.scrollTop;
    this.lyricContainer.classList.add('seeking');
    this.lyricView.classList.add('lyric-seeking');
    clearTimeout(this.lyricInteraction.exitTimer);
  }

  onLyricScroll() {
    if (this.lyricData.length === 0) {
      return;
    }

    if (!this.lyricInteraction.isPreviewing && Date.now() < this.lyricInteraction.autoScrollIgnoreUntil) {
      return;
    }

    if (!this.lyricInteraction.isPreviewing) {
      return;
    }

    if (Math.abs(this.lyricContainer.scrollTop - this.lyricInteraction.startScrollTop) > 2) {
      this.suppressDisplayToggle();
    }

    this.updateLyricPreviewLine();
    this.scheduleLyricPreviewExit();
  }

  updateLyricPreviewLine() {
    const centeredLine = findCenteredLyricLine(this.lyricContainer);
    if (!centeredLine) {
      return;
    }

    const previewIndex = Number.parseInt(centeredLine.dataset.lyricIndex, 10);
    const previewTime = Number.parseFloat(centeredLine.dataset.time);
    if (!Number.isFinite(previewIndex) || !Number.isFinite(previewTime)) {
      return;
    }

    this.lyricInteraction.previewIndex = previewIndex;
    this.lyricContainer.querySelectorAll('.lyric-line').forEach((line, index) => {
      line.classList.toggle('preview', index === previewIndex);
    });
  }

  exitLyricPreview() {
    clearTimeout(this.lyricInteraction.exitTimer);

    this.resetLyricInteraction();
    this.currentLyricIndex = -1;
    this.updateLyricHighlight();
  }

  scheduleLyricPreviewExit(delay = LYRIC_PREVIEW_IDLE_TIMEOUT) {
    clearTimeout(this.lyricInteraction.exitTimer);
    this.lyricInteraction.exitTimer = setTimeout(() => this.exitLyricPreview(), delay);
  }

  onLyricContainerClick(event) {
    if (!this.lyricInteraction.isPreviewing) {
      return;
    }

    const clickedLyricLine = event.target.closest('.lyric-line');
    if (!clickedLyricLine?.classList.contains('preview')) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    this.seekToLyricLine(clickedLyricLine);
  }

  onDisplayAreaClick(event) {
    if (this.shouldSuppressDisplayToggle()) {
      event.preventDefault();
      return;
    }

    if (this.lyricInteraction.isPreviewing) {
      event.preventDefault();
      return;
    }

    this.toggleDisplayView();
  }

  seekToLyricLine(lyricLine) {
    const time = Number.parseFloat(lyricLine?.dataset.time);
    if (!Number.isFinite(time)) {
      return;
    }

    this.audio.currentTime = time;
    this.suppressDisplayToggle();
    this.resetLyricInteraction();
    this.currentLyricIndex = -1;
    this.updateLyricHighlight();
  }

  canHandleLyricGesture() {
    return this.lyricData.length > 0 && this.isShowingLyric;
  }

  isActiveLyricPointer(event) {
    return this.lyricInteraction.pointerActive && event.pointerId === this.lyricInteraction.pointerId;
  }

  getLyricDragThreshold() {
    return this.lyricInteraction.pointerType === 'mouse'
      ? LYRIC_MOUSE_DRAG_THRESHOLD
      : LYRIC_TOUCH_DRAG_THRESHOLD;
  }

  getPreviewLineAtPoint(clientX, clientY) {
    if (!this.lyricInteraction.isPreviewing) {
      return null;
    }

    const target = document.elementFromPoint(clientX, clientY);
    const lyricLine = target?.closest?.('.lyric-line');
    return lyricLine?.classList.contains('preview') ? lyricLine : null;
  }

  suppressDisplayToggle(duration = LYRIC_CLICK_SUPPRESS_MS) {
    this.lyricInteraction.suppressDisplayToggleUntil = Date.now() + duration;
  }

  shouldSuppressDisplayToggle() {
    if (Date.now() >= this.lyricInteraction.suppressDisplayToggleUntil) {
      return false;
    }

    this.lyricInteraction.suppressDisplayToggleUntil = 0;
    return true;
  }

  clearLyricPointerState() {
    this.lyricInteraction.pointerActive = false;
    this.lyricInteraction.pointerId = null;
    this.lyricInteraction.pointerType = '';
  }

  resetLyricInteraction() {
    clearTimeout(this.lyricInteraction.exitTimer);
    Object.assign(this.lyricInteraction, {
      isPreviewing: false,
      pointerActive: false,
      pointerId: null,
      pointerType: '',
      previewIndex: -1,
    });
    this.lyricContainer.classList.remove('seeking');
    this.lyricView.classList.remove('lyric-seeking');
    this.lyricContainer.querySelectorAll('.lyric-line.preview').forEach(line => {
      line.classList.remove('preview');
    });
  }

  formatTime(milliseconds) {
    if (Number.isNaN(milliseconds)) {
      return '0:00';
    }
    const mins = Math.floor((milliseconds / 1000) / 60);
    const secs = Math.floor((milliseconds / 1000) % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  secondsToMilliseconds(seconds) {
    return Math.round((seconds || 0) * 1000);
  }

  toggleVolumePopup() {
    this.volumePopup.style.display = this.volumePopup.style.display === 'none' ? 'flex' : 'none';
  }

  onVolumeChange(event) {
    const volume = Number.parseInt(event.target.value, 10) / 100;
    this.audio.volume = volume;
    this.volumeValue.textContent = `${event.target.value}%`;

    const icon = this.btnVolume.querySelector('i');
    if (volume === 0) {
      icon.className = 'fa fa-volume-off';
    } else if (volume < 0.5) {
      icon.className = 'fa fa-volume-down';
    } else {
      icon.className = 'fa fa-volume-up';
    }
  }

  toggleDisplayView() {
    this.isShowingLyric = !this.isShowingLyric;

    if (this.isShowingLyric) {
      this.coverView.style.opacity = '0';
      this.coverView.style.transform = 'scale(0.9)';
      this.coverView.style.pointerEvents = 'none';
      this.lyricView.style.display = 'flex';
      this.lyricView.style.pointerEvents = 'auto';
      setTimeout(() => {
        this.lyricView.style.opacity = '1';
        this.lyricView.style.transform = 'scale(1)';
      }, 50);
    } else {
      this.lyricView.style.opacity = '0';
      this.lyricView.style.transform = 'scale(0.9)';
      this.lyricView.style.pointerEvents = 'none';
      setTimeout(() => {
        this.lyricView.style.display = 'none';
        this.coverView.style.pointerEvents = 'auto';
        this.coverView.style.opacity = '1';
        this.coverView.style.transform = 'scale(1)';
      }, 300);
    }
  }

  openSidebar() {
    this.sidebar.classList.add('active');
    this.sidebarOverlay.classList.add('active');
  }

  closeSidebar() {
    this.sidebar.classList.remove('active');
    this.sidebarOverlay.classList.remove('active');
  }

  rewindSeconds() {
    this.audio.currentTime = Math.max(0, this.audio.currentTime - 5);
  }

  forwardSeconds() {
    this.audio.currentTime = Math.min(this.audio.duration, this.audio.currentTime + 5);
  }

  switchSidebarTab(tabName) {
    this.sidebarTabButtons.forEach(button => {
      button.classList.toggle('active', button.dataset.tab === tabName);
    });

    this.sidebarPanes.forEach(pane => {
      pane.classList.toggle('active', pane.id === `sidebar-${tabName}`);
    });
  }

  markInPoint() {
    this.inPoint = this.audio.currentTime;
    this.inputInPoint.value = this.formatTime(this.secondsToMilliseconds(this.inPoint));
    return this.inPoint;
  }

  markOutPoint() {
    this.outPoint = this.audio.currentTime;
    this.inputOutPoint.value = this.formatTime(this.secondsToMilliseconds(this.outPoint));
    return this.outPoint;
  }

  clearMarkerInputs() {
    this.inPoint = null;
    this.outPoint = null;
    resetMarkerForm({
      inputInPoint: this.inputInPoint,
      inputOutPoint: this.inputOutPoint,
      inputMarkerLabel: this.inputMarkerLabel,
      inputMarkerColor: this.inputMarkerColor,
      btnCreateMarker: this.btnCreateMarker,
      defaultCreateMarkerHTML: this.defaultCreateMarkerHTML,
      markerPresets: this.markerPresets,
    });
  }

  async createMarker() {
    const label = this.inputMarkerLabel.value.trim();
    if (!label) {
      alert('请输入标记名称');
      return;
    }

    const editingMarkerId = this.btnCreateMarker.dataset.editingMarkerId
      ? Number.parseInt(this.btnCreateMarker.dataset.editingMarkerId, 10)
      : null;

    const markerData = buildMarkerPayload({
      label,
      color: this.inputMarkerColor.value,
      markerPresets: this.markerPresets,
      editingMarkerId,
      inPoint: this.inPoint,
      outPoint: this.outPoint,
      currentTime: this.audio.currentTime,
      secondsToMilliseconds: value => this.secondsToMilliseconds(value),
    });

    try {
      const response = await apiAddOrUpdateMarker(this.getCurrentFilePath(), markerData);
      if (response.success) {
        this.markers = response.markers;
        this.renderMarkers();
        this.clearMarkerInputs();
      } else {
        alert(`创建标记失败: ${response.error || '未知错误'}`);
      }
    } catch (error) {
      console.error('创建标记失败:', error);
      alert('创建标记失败，请检查网络连接');
    }
  }

  editMarker(marker) {
    if (marker.type === 1) {
      this.inPoint = marker.start / 1000;
      this.outPoint = marker.end / 1000;
    } else {
      this.inPoint = marker.time / 1000;
      this.outPoint = null;
    }

    populateMarkerForm({
      marker,
      inputInPoint: this.inputInPoint,
      inputOutPoint: this.inputOutPoint,
      inputMarkerLabel: this.inputMarkerLabel,
      inputMarkerColor: this.inputMarkerColor,
      btnCreateMarker: this.btnCreateMarker,
      formatTime: value => this.formatTime(value),
    });
    this.switchSidebarTab('marker');
    alert('标记已加载到编辑面板，修改后点击"创建"按钮更新');
  }

  async deleteMarker(marker) {
    if (!confirm(`确定要删除标记"${marker.label}" 吗？`)) {
      return;
    }

    try {
      const response = await apiDeleteMarker(this.getCurrentFilePath(), marker.id);
      if (response.success) {
        this.markers = response.markers;
        this.renderMarkers();
      } else {
        alert(`删除标记失败: ${response.error || '未知错误'}`);
      }
    } catch (error) {
      console.error('删除标记失败:', error);
      alert('删除标记失败，请检查网络连接');
    }
  }

  goBack() {
    window.history.back();
  }
}
