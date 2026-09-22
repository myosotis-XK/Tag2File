import { apiAddTag, apiGetCategories, apiGetFileTags } from '../api.js';
import { globalState } from '../state.js';

const LONG_PRESS_MS = 550;
const MOVE_TOLERANCE_PX = 10;
const EXCLUDED_CATEGORIES = new Set(['文件类型']);

let modalElement = null;
let modalInstance = null;
let activeFilePath = null;
let activeExistingTags = new Set();
let submitting = false;
let noticeTimer = null;

function ensureModal() {
    if (modalElement) {
        return modalElement;
    }

    modalElement = document.createElement('div');
    modalElement.className = 'modal fade';
    modalElement.id = 'file-tagging-modal';
    modalElement.tabIndex = -1;
    modalElement.setAttribute('aria-hidden', 'true');
    modalElement.innerHTML = `
        <div class="modal-dialog modal-dialog-scrollable modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <div class="file-tagging-header-text">
                        <h5 class="modal-title">选择标签</h5>
                        <div class="file-tagging-file-name text-muted small"></div>
                        <div class="file-tagging-existing-tags" aria-label="已有标签"></div>
                    </div>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="关闭"></button>
                </div>
                <div class="modal-body file-tagging-body"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modalElement);

    modalInstance = window.bootstrap.Modal.getOrCreateInstance(modalElement);
    modalElement.addEventListener('hidden.bs.modal', () => {
        activeFilePath = null;
        activeExistingTags.clear();
        submitting = false;
    });
    return modalElement;
}

function showNotice(message, tone = 'success') {
    let notice = document.getElementById('file-tagging-notice');
    if (!notice) {
        notice = document.createElement('div');
        notice.id = 'file-tagging-notice';
        notice.setAttribute('role', 'status');
        document.body.appendChild(notice);
    }

    notice.className = `file-tagging-notice alert alert-${tone}`;
    notice.textContent = message;
    notice.classList.add('show');

    if (noticeTimer) {
        window.clearTimeout(noticeTimer);
    }
    noticeTimer = window.setTimeout(() => notice.classList.remove('show'), 2200);
}

function setTagButtonsDisabled(disabled) {
    modalElement
        ?.querySelectorAll('.file-tagging-tag')
        .forEach(button => {
            button.disabled = disabled;
        });
}

function renderExistingTags(tags) {
    const container = modalElement.querySelector('.file-tagging-existing-tags');
    container.replaceChildren();

    activeExistingTags = new Set(Array.isArray(tags) ? tags : []);
    const sortedTags = Array.from(activeExistingTags).sort((left, right) => left.localeCompare(right, 'zh-CN'));
    if (sortedTags.length === 0) {
        const empty = document.createElement('span');
        empty.className = 'file-tagging-existing-empty';
        empty.textContent = '暂无标签';
        container.appendChild(empty);
        return;
    }

    sortedTags.forEach(tag => {
        const badge = document.createElement('span');
        badge.className = 'file-tagging-existing-tag';
        badge.textContent = tag;
        container.appendChild(badge);
    });
}

async function submitTag(filePath, tag) {
    if (submitting || filePath !== activeFilePath) {
        return;
    }
    if (!globalState.currentDatabasePath) {
        showNotice('当前标签库不可用，请刷新页面后重试', 'danger');
        return;
    }

    submitting = true;
    setTagButtonsDisabled(true);
    try {
        const response = await apiAddTag({
            dbPath: globalState.currentDatabasePath,
            tag,
            filePaths: [filePath],
        });
        if (!response.data?.success) {
            throw new Error(response.data?.message || '打标签失败');
        }
        activeExistingTags.add(tag);
        renderExistingTags(Array.from(activeExistingTags));
        showNotice(`已添加标签：${tag}`);
        submitting = false;
        setTagButtonsDisabled(false);
    } catch (error) {
        console.error('打标签失败:', error);
        const message = error.response?.data?.message || error.message || '打标签失败，请重试';
        showNotice(message, 'danger');
        submitting = false;
        setTagButtonsDisabled(false);
    }
}

function renderTagOptions(filePath, data) {
    const body = modalElement.querySelector('.file-tagging-body');
    body.replaceChildren();

    const categories = data?.categories || {};
    const categoryOrder = Array.isArray(data?.category_order) ? data.category_order : [];
    let renderedTagCount = 0;

    categoryOrder.forEach(category => {
        if (EXCLUDED_CATEGORIES.has(category)) {
            return;
        }
        const tags = Array.isArray(categories[category]?.tags) ? categories[category].tags : [];
        if (tags.length === 0) {
            return;
        }

        const section = document.createElement('section');
        section.className = 'file-tagging-category';

        const heading = document.createElement('div');
        heading.className = 'file-tagging-category-title';
        heading.textContent = category;
        section.appendChild(heading);

        const tagList = document.createElement('div');
        tagList.className = 'file-tagging-tag-list';
        tags.forEach(tag => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-outline-primary btn-sm file-tagging-tag';
            button.textContent = tag;
            button.addEventListener('click', () => submitTag(filePath, tag));
            tagList.appendChild(button);
            renderedTagCount += 1;
        });
        section.appendChild(tagList);
        body.appendChild(section);
    });

    if (renderedTagCount === 0) {
        const empty = document.createElement('div');
        empty.className = 'text-center text-muted py-4';
        empty.textContent = '当前标签库没有可用标签';
        body.appendChild(empty);
    }
}

async function openTagSelector(file) {
    ensureModal();
    activeFilePath = file.filePath;
    submitting = false;

    modalElement.querySelector('.file-tagging-file-name').textContent = file.fileName;
    const existingTags = modalElement.querySelector('.file-tagging-existing-tags');
    existingTags.replaceChildren();
    const loadingExistingTags = document.createElement('span');
    loadingExistingTags.className = 'file-tagging-existing-empty';
    loadingExistingTags.textContent = '读取已有标签...';
    existingTags.appendChild(loadingExistingTags);
    const body = modalElement.querySelector('.file-tagging-body');
    body.innerHTML = `
        <div class="loading py-4">
            <div class="spinner"></div>
            <p>加载标签中...</p>
        </div>
    `;
    modalInstance.show();

    const [categoriesResult, existingTagsResult] = await Promise.allSettled([
        apiGetCategories(),
        apiGetFileTags(file.filePath),
    ]);
    if (activeFilePath !== file.filePath) {
        return;
    }

    if (existingTagsResult.status === 'fulfilled') {
        renderExistingTags(existingTagsResult.value.data?.tags);
    } else {
        console.error('读取已有标签失败:', existingTagsResult.reason);
        existingTags.replaceChildren();
        const errorText = document.createElement('span');
        errorText.className = 'file-tagging-existing-error';
        errorText.textContent = '已有标签读取失败';
        existingTags.appendChild(errorText);
    }

    if (categoriesResult.status === 'fulfilled') {
        renderTagOptions(file.filePath, categoriesResult.value.data);
    } else {
        console.error('加载标签失败:', categoriesResult.reason);
        body.replaceChildren();
        const message = document.createElement('div');
        message.className = 'text-center text-danger py-4';
        message.textContent = '加载标签失败，请重试';
        body.appendChild(message);
    }
}

/**
 * 为文件缩略图绑定长按打标签手势。
 * 返回的 consumeClick() 用于阻止长按松手后继续触发“打开文件”。
 */
export function attachFileTaggingGesture(element, file) {
    let timer = null;
    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let suppressClickUntil = 0;

    const cancelTimer = () => {
        if (timer !== null) {
            window.clearTimeout(timer);
            timer = null;
        }
        pointerId = null;
    };

    const handleLongPress = async (suppressClick = true) => {
        timer = null;
        if (suppressClick) {
            suppressClickUntil = Date.now() + 1000;
        }
        await openTagSelector(file);
    };

    element.addEventListener('pointerdown', event => {
        if (!event.isPrimary || event.button !== 0) {
            return;
        }
        cancelTimer();
        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        timer = window.setTimeout(handleLongPress, LONG_PRESS_MS);
    });

    element.addEventListener('pointermove', event => {
        if (event.pointerId !== pointerId || timer === null) {
            return;
        }
        if (
            Math.abs(event.clientX - startX) > MOVE_TOLERANCE_PX
            || Math.abs(event.clientY - startY) > MOVE_TOLERANCE_PX
        ) {
            cancelTimer();
        }
    });

    element.addEventListener('pointerup', cancelTimer);
    element.addEventListener('pointercancel', cancelTimer);
    element.addEventListener('pointerleave', event => {
        if (event.pointerType === 'mouse') {
            cancelTimer();
        }
    });

    // 桌面浏览器可用右键打开同一个标签选择框，同时关闭移动端原生长按菜单。
    element.addEventListener('contextmenu', event => {
        event.preventDefault();
        if (Date.now() < suppressClickUntil) {
            return;
        }
        handleLongPress(false);
    });

    return {
        consumeClick() {
            if (Date.now() >= suppressClickUntil) {
                suppressClickUntil = 0;
                return false;
            }
            suppressClickUntil = 0;
            return true;
        },
    };
}
