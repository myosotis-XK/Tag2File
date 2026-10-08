export { getAdjacentPlaylistIndex } from './audioPlayerContext.js';

const KEY = 'tag2file.videoPlayer.context';
export const PLAY_MODES = [
    { label: '顺序播放', icon: 'repeat' },
    { label: '随机播放', icon: 'shuffle' },
    { label: '单个循环', icon: 'repeat_one' },
];

export function isVideoFile(path) {
    return typeof path === 'string' && /\.mp4$/i.test(path);
}

export function videoFiles(paths) {
    return [...new Set(paths.filter(isVideoFile).map(path => path.replace(/\\/g, '/')))];
}

export function normalizeVideoContext(context) {
    if (!context || !Array.isArray(context.playlist)) return null;
    const current = context.playlist[context.currentIndex]?.replace?.(/\\/g, '/');
    const playlist = videoFiles(context.playlist);
    const availableFiles = videoFiles([...(Array.isArray(context.availableFiles) ? context.availableFiles : []), ...playlist]);
    const currentIndex = playlist.length ? Math.max(0, playlist.indexOf(current)) : -1;
    return { playlist, availableFiles, currentIndex };
}

export function saveVideoPlayerContext(context, storage = sessionStorage) {
    const normalized = normalizeVideoContext(context);
    if (!normalized) return false;
    try {
        storage.setItem(KEY, JSON.stringify(normalized));
        return true;
    } catch {
        return false;
    }
}

export function loadVideoPlayerContext() {
    try {
        return normalizeVideoContext(JSON.parse(sessionStorage.getItem(KEY)));
    } catch {
        return null;
    }
}

export function formatVideoTime(seconds) {
    const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
    const hours = Math.floor(total / 3600);
    const minutes = String(Math.floor(total / 60) % 60).padStart(2, '0');
    const remainder = String(total % 60).padStart(2, '0');
    return hours ? `${hours}:${minutes}:${remainder}` : `${minutes}:${remainder}`;
}
