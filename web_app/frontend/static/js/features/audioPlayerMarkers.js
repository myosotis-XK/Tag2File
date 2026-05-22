export function renderPresetItems({ markerPresets, presetGrid, emptyHTML, onSelect }) {
  if (markerPresets.length === 0) {
    presetGrid.innerHTML = emptyHTML;
    return;
  }

  presetGrid.innerHTML = markerPresets.map(preset => `
    <div class="preset-item" data-preset-id="${preset.id}" data-preset-name="${preset.name}" data-preset-color="${preset.color}" style="border-left-color: ${preset.color};">
      <div class="preset-color" style="background-color: ${preset.color};"></div>
      <span class="preset-name">${preset.name}</span>
    </div>
  `).join('');

  presetGrid.querySelectorAll('.preset-item').forEach(item => {
    item.addEventListener('click', () => {
      onSelect({
        id: Number.parseInt(item.dataset.presetId, 10),
        name: item.dataset.presetName,
        color: item.dataset.presetColor,
      });
    });
  });
}

export function renderMarkerItems({
  markers,
  markerList,
  emptyHTML,
  formatTime,
  onSeek,
  onEdit,
  onDelete,
}) {
  if (markers.length === 0) {
    markerList.innerHTML = emptyHTML;
    return;
  }

  markerList.innerHTML = markers.map(marker => {
    const timeText = marker.type === 0
      ? formatTime(marker.time)
      : `${formatTime(marker.start)} - ${formatTime(marker.end)}`;
    const jumpTime = marker.type === 0 ? marker.time : marker.start;

    return `
      <div class="marker-item" data-marker-id="${marker.id}" data-time="${jumpTime}">
        <div class="marker-color" style="background: ${marker.color}"></div>
        <div class="marker-info">
          <div class="marker-time">${timeText}</div>
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

  markerList.querySelectorAll('.marker-item').forEach(element => {
    const markerId = Number.parseInt(element.dataset.markerId, 10);
    const marker = markers.find(item => item.id === markerId);

    element.querySelector('.marker-info').addEventListener('click', () => {
      onSeek(Number.parseFloat(element.dataset.time));
    });
    element.querySelector('.btn-edit-marker').addEventListener('click', event => {
      event.stopPropagation();
      onEdit(marker);
    });
    element.querySelector('.btn-delete-marker').addEventListener('click', event => {
      event.stopPropagation();
      onDelete(marker);
    });
  });
}

export function resetMarkerForm({
  inputInPoint,
  inputOutPoint,
  inputMarkerLabel,
  inputMarkerColor,
  btnCreateMarker,
  defaultCreateMarkerHTML,
  markerPresets,
}) {
  inputInPoint.value = '';
  inputOutPoint.value = '';
  inputMarkerLabel.value = '';
  inputMarkerColor.value = markerPresets.length > 0 ? markerPresets[0].color : '#ff0000';
  btnCreateMarker.innerHTML = defaultCreateMarkerHTML;
  delete btnCreateMarker.dataset.editingMarkerId;
}

export function populateMarkerForm({
  marker,
  inputInPoint,
  inputOutPoint,
  inputMarkerLabel,
  inputMarkerColor,
  btnCreateMarker,
  formatTime,
}) {
  if (marker.type === 1) {
    inputInPoint.value = formatTime(marker.start);
    inputOutPoint.value = formatTime(marker.end);
  } else {
    inputInPoint.value = formatTime(marker.time);
    inputOutPoint.value = '';
  }

  inputMarkerLabel.value = marker.label;
  inputMarkerColor.value = marker.color;
  btnCreateMarker.innerHTML = '<i class="fa fa-save"></i> 更新';
  btnCreateMarker.dataset.editingMarkerId = String(marker.id);
}

export function buildMarkerPayload({
  label,
  color,
  markerPresets,
  editingMarkerId,
  inPoint,
  outPoint,
  currentTime,
  secondsToMilliseconds,
}) {
  const preset = markerPresets.find(item => item.color === color);
  const hasRange = inPoint !== null && outPoint !== null;
  const pointSeconds = inPoint ?? currentTime;
  const startSeconds = inPoint ?? 0;
  const endSeconds = outPoint ?? 0;

  return {
    id: editingMarkerId,
    type: hasRange ? 1 : 0,
    label,
    color,
    preset_id: preset?.id || null,
    time: secondsToMilliseconds(hasRange ? startSeconds : pointSeconds),
    start: secondsToMilliseconds(startSeconds),
    end: secondsToMilliseconds(endSeconds),
  };
}
