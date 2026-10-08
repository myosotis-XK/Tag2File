import { apiUploadFile } from '../api.js';
import { globalState } from '../state.js';
import { loadFolderContents } from './virtualGrid.js';

export function setupFileUpload() {
    const button = document.getElementById('upload-files-btn');
    const input = document.getElementById('upload-files-input');
    const status = document.getElementById('upload-status');
    let destination = null;
    let uploading = false;

    function showStatus(message, tone = 'info') {
        status.className = `alert alert-${tone}`;
        status.textContent = message;
    }

    button.addEventListener('click', () => {
        if (uploading || globalState.browseMode !== 'folder_browse' || !globalState.currentFolder) return;
        destination = globalState.currentFolder;
        input.value = '';
        input.click();
    });

    input.addEventListener('change', async () => {
        const files = Array.from(input.files || []);
        const folderPath = destination;
        if (uploading || !folderPath || !files.length) return;
        uploading = true;
        button.disabled = true;
        button.textContent = '上传中…';
        let completed = 0;
        const failures = [];

        try {
            for (const [index, file] of files.entries()) {
                const label = `上传到：${folderPath}\n正在上传 ${index + 1}/${files.length}：${file.name}`;
                showStatus(label);
                try {
                    await apiUploadFile({
                        folderPath,
                        file,
                        onUploadProgress: ({ loaded, total }) => {
                            const progress = total ? Math.min(100, Math.round(loaded / total * 100)) : null;
                            showStatus(`${label}${progress === null ? '' : `（${progress}%）`}${progress === 100 ? '，正在保存…' : ''}`);
                        },
                    });
                    completed += 1;
                } catch (error) {
                    const message = error.response?.data?.message || '连接中断或上传失败，请刷新目录确认后重试';
                    failures.push(`${file.name}：${message}`);
                    if (error.response?.status === 401) break;
                }
            }
            const remaining = files.length - completed;
            showStatus(`上传到：${folderPath}\n已成功上传 ${completed}/${files.length} 个文件。${remaining ? ` ${remaining} 个文件未确认上传成功。\n${failures.join('\n')}` : ''}`,
                remaining ? 'warning' : 'success');

            if (globalState.browseMode === 'folder_browse' && globalState.currentFolder === folderPath) {
                await loadFolderContents(folderPath, { preserveRoot: true, onlyIfCurrentFolder: true });
            }
        } finally {
            uploading = false;
            button.disabled = false;
            button.innerHTML = '<i class="fa fa-upload" aria-hidden="true"></i> 上传文件';
            input.value = '';
        }
    });
}
