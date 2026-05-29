import { globalState, initializeState, saveUISettings } from './state.js';
import { insertAtCursor, debounce } from './utils.js';
import { searchFiles, clearSearch } from './features/search.js';
import { goParentOrRestore, loadFolderContents, persistMainViewState, renderBrowseNav, restorePersistedMainViewState, restoreSearchSnapshot, setupVirtualGrid } from './features/virtualGrid.js';
import { loadDatabaseList } from './features/database.js';

// 更新按钮样式以反映当前设置
function updateButtonStyles() {
    // 更新图标大小按钮样式
    document.querySelectorAll('.size-btn').forEach(btn => {
        const size = btn.getAttribute('data-size');
        if (size === globalState.currentIconSize) {
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-outline-primary', 'active');
        } else {
            btn.classList.remove('btn-outline-primary', 'active');
            btn.classList.add('btn-outline-secondary');
        }
    });
    
    // 更新排序键按钮样式
    document.querySelectorAll('.sort-btn').forEach(btn => {
        const sortKey = btn.getAttribute('data-sort');
        if (sortKey === globalState.currentSortKey) {
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-outline-primary', 'active');
        } else {
            btn.classList.remove('btn-outline-primary', 'active');
            btn.classList.add('btn-outline-secondary');
        }
    });
    
    // 更新排序顺序按钮样式
    document.querySelectorAll('.order-btn').forEach(btn => {
        const sortOrder = btn.getAttribute('data-order');
        if (sortOrder === globalState.currentSortOrder) {
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-outline-primary', 'active');
        } else {
            btn.classList.remove('btn-outline-primary', 'active');
            btn.classList.add('btn-outline-secondary');
        }
    });
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化全局状态，包括从后端加载用户设置
    await initializeState();
    
    // 设置初始图标大小
    document.documentElement.style.setProperty('--thumb-size', globalState.sizeMap[globalState.currentIconSize] + 'px');
    
    // 更新按钮样式以反映当前设置
    updateButtonStyles();

    document.querySelectorAll('.operator-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const searchInput = document.getElementById('search-input');
            insertAtCursor(searchInput, btn.textContent);
        });
    });

    document.querySelectorAll('.size-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const newSize = this.getAttribute('data-size');
            if (newSize !== globalState.currentIconSize) {
                // 1. 更新全局状态
                globalState.currentIconSize = newSize;

                // 2. 保存设置到后端
                await saveUISettings();
                
                // 3. 更新按钮样式
                document.querySelectorAll('.size-btn').forEach(b => {
                    b.classList.remove('btn-outline-primary', 'active');
                    b.classList.add('btn-outline-secondary');
                });
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-outline-primary', 'active');
                
                // 4. 重新渲染网格
                if (globalState.virtualFiles.length > 0) {
                    // 重新设置网格（将强制刷新）
                    setupVirtualGrid();
                }
            }
        });
    });

        // 排序按钮点击事件
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const newSortKey = this.getAttribute('data-sort');
            if (newSortKey !== globalState.currentSortKey) {
                // 1. 更新全局状态
                globalState.currentSortKey = newSortKey;

                // 2. 保存设置到后端
                await saveUISettings();
                
                // 3. 更新按钮样式
                document.querySelectorAll('.sort-btn').forEach(b => {
                    b.classList.remove('btn-outline-primary', 'active');
                    b.classList.add('btn-outline-secondary');
                });
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-outline-primary', 'active');
                
                // 4. 搜索模式重新搜索，文件夹浏览模式重新加载当前目录。
                if (globalState.browseMode === 'folder_browse' && globalState.currentFolder) {
                    await loadFolderContents(globalState.currentFolder, { preserveRoot: true });
                } else if (document.getElementById('search-input').value.trim() !== '') {
                    searchFiles();
                }
            }
        });
    });
    
    // 排序顺序按钮点击事件
    document.querySelectorAll('.order-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const newSortOrder = this.getAttribute('data-order');
            if (newSortOrder !== globalState.currentSortOrder) {
                // 1. 更新全局状态
                globalState.currentSortOrder = newSortOrder;

                // 2. 保存设置到后端
                await saveUISettings();
                
                // 3. 更新按钮样式
                document.querySelectorAll('.order-btn').forEach(b => {
                    b.classList.remove('btn-outline-primary', 'active');
                    b.classList.add('btn-outline-secondary');
                });
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-outline-primary', 'active');
                
                // 4. 搜索模式重新搜索，文件夹浏览模式重新加载当前目录。
                if (globalState.browseMode === 'folder_browse' && globalState.currentFolder) {
                    await loadFolderContents(globalState.currentFolder, { preserveRoot: true });
                } else if (document.getElementById('search-input').value.trim() !== '') {
                    searchFiles();
                }
            }
        });
    });

    // 1️⃣ 初始化 CSS 变量，确保第一次渲染生效
    document.documentElement.style.setProperty('--thumb-size', globalState.sizeMap[globalState.currentIconSize] + 'px');
    
    initEventListeners();
    await loadDatabaseList();
    restorePersistedMainViewState();
    renderBrowseNav();

    // 阻止点击特定区域时关闭父级下拉菜单的逻辑
    const keepOpenElements = document.querySelectorAll('.keep-open-on-click');
    keepOpenElements.forEach(element => {
        // 阻止点击其内部元素时，关闭整个“设置”菜单
        element.addEventListener('click', (e) => {
            // 阻止事件冒泡到父级的 dropdown 处理器
            e.stopPropagation();
        });
    });
    // 监听窗口大小变化
    window.addEventListener('resize', debounce(() => {
        // 只有在有文件（即虚拟列表已初始化）时才重新渲染
        if (globalState.virtualFiles && globalState.virtualFiles.length > 0) {
            setupVirtualGrid();
        }
    }, 150)); // 150ms 防抖
    window.addEventListener('beforeunload', persistMainViewState);
});

// 初始化事件监听
function initEventListeners() {
    // 搜索按钮点击事件
    document.getElementById('search-btn').addEventListener('click', searchFiles);
    document.getElementById('restore-search-btn').addEventListener('click', restoreSearchSnapshot);
    document.getElementById('go-parent-btn').addEventListener('click', goParentOrRestore);
    
    // 搜索输入框回车事件
    document.getElementById('search-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchFiles();
        }
    });
    
    // 清空搜索按钮点击事件
    document.getElementById('clear-search').addEventListener('click', clearSearch);
    
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    let backdrop = document.querySelector('.sidebar-backdrop');

    // 如果遮罩层不存在，则创建它
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.className = 'sidebar-backdrop';
        document.body.appendChild(backdrop);
    }

    // 切换侧边栏状态
    function toggleSidebar() {
        sidebar.classList.toggle('show');
        backdrop.classList.toggle('show');
    }

    // 绑定按钮点击事件
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    // 绑定遮罩层点击事件（点击遮罩层关闭侧边栏）
    if (backdrop) {
        backdrop.addEventListener('click', toggleSidebar);
    }
}
