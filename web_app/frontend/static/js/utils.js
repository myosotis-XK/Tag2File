/**
 * 路径处理：从完整路径中提取文件名或数据库名
 * @param {string} path - 原始路径字符串
 * @returns {string} - 提取后的名称
 */
export function extractDbName(path) {
    if (!path) return 'N/A';
    // 兼容 Windows (\) 和 Unix (/) 路径分隔符
    const parts = path.replace(/\\/g, '/').split('/');
    return parts[parts.length - 1] || path;
}

/**
 * 光标位置插入文本：在输入框的当前光标位置插入指定字符串
 * @param {HTMLInputElement|HTMLTextAreaElement} input - 输入框元素
 * @param {string} text - 要插入的文本
 */
export function insertAtCursor(input, text) {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const before = input.value.substring(0, start);
    const after = input.value.substring(end, input.value.length);
    
    input.value = before + text + after;
    
    // 重新设置光标位置到新插入文本之后
    const newPos = start + text.length;
    input.setSelectionRange(newPos, newPos);
    input.focus();
}

/**
 * 节流函数 (Throttle)：规定时间内只执行一次，用于滚动监听
 * @param {Function} func - 目标函数
 * @param {number} limit - 限制时间(ms)
 */
export function throttle(func, limit) {
    let timeoutId;
    let lastExecuted = 0;

    return function(...args) {
        const context = this;
        const now = Date.now();
        const remaining = limit - (now - lastExecuted);

        clearTimeout(timeoutId);

        if (remaining <= 0 || remaining > limit) {
            lastExecuted = now;
            func.apply(context, args);
        } else {
            timeoutId = setTimeout(() => {
                lastExecuted = Date.now();
                func.apply(context, args);
            }, remaining);
        }
    };
}

/**
 * 防抖函数 (Debounce)：在事件停止触发一段时间后执行，用于窗口 Resize
 * @param {Function} func - 目标函数
 * @param {number} wait - 等待时间(ms)
 */
export function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

/**
 * 文件类型图标映射表
 * (将其放在 utils 中作为常量，方便在 tagTree.js 中引用)
 */
export const FILE_TYPE_ICON_MAP = {
    '图片': 'fa-image',
    '视频': 'fa-film',
    '音频': 'fa-music',
    '其他': 'fa-file-o'
};