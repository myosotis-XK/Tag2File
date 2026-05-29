export function parseLyricContent(lrcContent) {
  return lrcContent
    .split('\n')
    .map(line => {
      const match = line.match(/\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\](.*)/);
      if (!match) {
        return null;
      }

      const minutes = Number.parseInt(match[1], 10);
      const seconds = Number.parseInt(match[2], 10);
      const millisecondsText = match[3] || '0';
      const milliseconds = Number.parseInt(millisecondsText.padEnd(3, '0').slice(0, 3), 10);
      const text = match[4].trim();
      if (!text) {
        return null;
      }

      return {
        time: minutes * 60 + seconds + milliseconds / 1000,
        text,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);
}

export function renderLyricLines({ lyricData, lyricContainer, emptyHTML, onSeek }) {
  if (lyricData.length === 0) {
    lyricContainer.innerHTML = emptyHTML;
    return;
  }

  lyricContainer.innerHTML = lyricData.map((line, index) => `
    <div class="lyric-line" data-lyric-index="${index}" data-time="${line.time}">
      ${line.text}
    </div>
  `).join('');

  lyricContainer.querySelectorAll('.lyric-line').forEach(element => {
    element.addEventListener('click', event => {
      event.stopPropagation();
      onSeek(Number.parseFloat(element.dataset.time));
    });
  });
}

export function updateLyricActiveLine({
  lyricData,
  lyricContainer,
  currentTime,
  currentLyricIndex,
  shouldAutoScroll = true,
}) {
  if (lyricData.length === 0) {
    return currentLyricIndex;
  }

  let newIndex = -1;
  for (let i = 0; i < lyricData.length; i += 1) {
    if (i === lyricData.length - 1 || currentTime < lyricData[i + 1].time) {
      newIndex = i;
      break;
    }
  }

  if (newIndex === currentLyricIndex) {
    return currentLyricIndex;
  }

  lyricContainer.querySelectorAll('.lyric-line').forEach((line, index) => {
    if (index === newIndex) {
      line.classList.add('active');
      if (shouldAutoScroll) {
        line.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else {
      line.classList.remove('active');
    }
  });

  return newIndex;
}

export function findCenteredLyricLine(lyricContainer) {
  const lines = [...lyricContainer.querySelectorAll('.lyric-line')];
  if (lines.length === 0) {
    return null;
  }

  const containerRect = lyricContainer.getBoundingClientRect();
  const centerY = containerRect.top + containerRect.height / 2;
  let nearestLine = null;
  let nearestDistance = Number.POSITIVE_INFINITY;

  lines.forEach(line => {
    const rect = line.getBoundingClientRect();
    const lineCenterY = rect.top + rect.height / 2;
    const distance = Math.abs(lineCenterY - centerY);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestLine = line;
    }
  });

  return nearestLine;
}
