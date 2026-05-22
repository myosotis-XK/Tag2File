const AUDIO_PLAYER_CONTEXT_KEY = 'tag2file.audioPlayer.context';

function normalizePlaylistContext(context) {
  if (!context || !Array.isArray(context.playlist) || context.playlist.length === 0) {
    return null;
  }

  const playlist = context.playlist.filter(path => typeof path === 'string' && path.trim());
  if (playlist.length === 0) {
    return null;
  }

  const parsedIndex = Number.parseInt(context.currentIndex, 10);
  const currentIndex = Number.isInteger(parsedIndex)
    ? Math.min(Math.max(parsedIndex, 0), playlist.length - 1)
    : 0;

  return { playlist, currentIndex };
}

export function saveAudioPlayerContext(context) {
  const normalized = normalizePlaylistContext(context);
  if (!normalized) {
    return false;
  }

  sessionStorage.setItem(AUDIO_PLAYER_CONTEXT_KEY, JSON.stringify(normalized));
  return true;
}

export function loadAudioPlayerContext() {
  try {
    const raw = sessionStorage.getItem(AUDIO_PLAYER_CONTEXT_KEY);
    if (!raw) {
      return null;
    }
    return normalizePlaylistContext(JSON.parse(raw));
  } catch (error) {
    console.warn('Failed to load audio player context from sessionStorage:', error);
    return null;
  }
}

export function updateAudioPlayerIndex(currentIndex) {
  const context = loadAudioPlayerContext();
  if (!context) {
    return false;
  }
  return saveAudioPlayerContext({ ...context, currentIndex });
}

export function loadLegacyAudioPlayerContext(search = window.location.search) {
  const params = new URLSearchParams(search);
  const playlistParam = params.get('playlist');
  const indexParam = params.get('index');

  if (!playlistParam) {
    return null;
  }

  try {
    return normalizePlaylistContext({
      playlist: JSON.parse(decodeURIComponent(playlistParam)),
      currentIndex: indexParam,
    });
  } catch (error) {
    console.warn('Failed to parse legacy audio player context from URL:', error);
    return null;
  }
}

export function getAdjacentPlaylistIndex(playMode, playlistLength, currentIndex, direction = 1) {
  if (playlistLength <= 0) {
    return -1;
  }

  if (playMode === 1 && playlistLength > 1) {
    const candidates = Array.from({ length: playlistLength }, (_, index) => index)
      .filter(index => index !== currentIndex);
    return candidates[Math.floor(Math.random() * candidates.length)];
  }

  const safeIndex = Math.min(Math.max(currentIndex, 0), playlistLength - 1);
  const step = direction < 0 ? -1 : 1;
  return (safeIndex + step + playlistLength) % playlistLength;
}
