export function renderPlaylistItems({
  playlist,
  playlistMetadata,
  playlistContainer,
  emptyHTML,
  currentIndex,
  onSelect,
}) {
  if (playlist.length === 0) {
    playlistContainer.innerHTML = emptyHTML;
    return;
  }

  playlistContainer.innerHTML = playlist.map((filePath, index) => {
    const metadata = playlistMetadata?.[index];
    const title = metadata?.title || filePath.split('/').pop();
    const isPlaying = index === currentIndex;

    return `
      <div class="playlist-item ${isPlaying ? 'playing' : ''}" data-index="${index}">
        <span class="playlist-title">${title}</span>
      </div>
    `;
  }).join('');

  playlistContainer.querySelectorAll('.playlist-item').forEach(element => {
    element.addEventListener('click', () => {
      onSelect(Number.parseInt(element.dataset.index, 10));
    });
  });
}

export function updatePlaylistPlayingState({ playlistContainer, currentIndex }) {
  playlistContainer.querySelectorAll('.playlist-item').forEach((item, index) => {
    item.classList.toggle('playing', index === currentIndex);
  });
}
