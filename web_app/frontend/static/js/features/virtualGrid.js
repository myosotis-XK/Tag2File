import { globalState, saveUISettings } from '../state.js';
import { apiGetThumbnail, apiOpenFile, apiSearchFiles } from '../api.js';
import { throttle } from '../utils.js';

// 检测是否为音频文件
function isAudioFile(filePath) {
    const ext = filePath.split('.').pop().toLowerCase();
    return ['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg', 'wma', 'ape'].includes(ext);
}

// 检测是否为文件夹（通过后端API）
async function isDirectory(filePath) {
    try {
        const response = await fetch('/is_folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_path: filePath })
        });
        
        if (response.ok) {
            const data = await response.json();
            return data.is_folder === true;
        } else {
            console.error('检测文件夹失败:', response.statusText);
            // 如果API失败，使用简单的备用逻辑
            return filePath.endsWith('/') || filePath.endsWith('\\');
        }
    } catch (error) {
        console.error('检测文件夹错误:', error);
        // 如果网络错误，使用简单的备用逻辑
        return filePath.endsWith('/') || filePath.endsWith('\\');
    }
}

// 获取文件夹内容
async function getFolderContents(folderPath) {
    try {
        const response = await fetch('/get_folder_contents', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ folder_path: folderPath })
        });
        
        if (response.ok) {
            const data = await response.json();
            return data.files || [];
        } else {
            console.error('获取文件夹内容失败:', response.statusText);
            return [];
        }
    } catch (error) {
        console.error('获取文件夹内容错误:', error);
        return [];
    }
}

// 核心渲染函数：设置和渲染虚拟网格
export function setupVirtualGrid() {
    const resultsContainer = document.getElementById('results-container');
    let container = document.getElementById('virtual-container');
    let grid = document.getElementById('virtual-grid');
    
    // 如果文件列表为空
    if (globalState.virtualFiles.length === 0) {
        resultsContainer.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="fa fa-folder-open-o fa-3x mb-3"></i>
                <p>未找到匹配的文件</p>
            </div>
        `;
        return;
    }
    
    // 首次渲染或切换尺寸时重建容器
    if (!container || !grid) {
        resultsContainer.innerHTML = '';
        
        // 动态高度容器
        container = document.createElement('div');
        container.id = 'virtual-container';
        container.style.overflowY = 'auto';
        container.style.position = 'relative';
        resultsContainer.appendChild(container);
        
        // 网格容器
        grid = document.createElement('div');
        grid.id = 'virtual-grid';
        grid.style.position = 'relative';
        grid.style.width = '100%';
        container.appendChild(grid);
        
        // 绑定滚动事件
        const SCROLL_THROTTLE_LIMIT = 200; // 200ms 节流

        if (!container._throttledRender) {
            // 创建一个节流后的渲染函数
            container._throttledRender = throttle(renderVisibleItems, SCROLL_THROTTLE_LIMIT);

            // 绑定事件
            container.addEventListener('scroll', container._throttledRender);
        }
    }
    
    // --- 动态高度计算和 CSS 变量更新 ---
    const topOffset = container.getBoundingClientRect().top;
    const availableHeight = window.innerHeight - topOffset - 100; // 减去 20px 作为底部间距
    container.style.height = Math.max(400, availableHeight) + 'px'; // 设置最小高度 400px
    document.documentElement.style.setProperty('--thumb-size', globalState.sizeMap[globalState.currentIconSize] + 'px'); // 更新 CSS 变量
    
    // --- 虚拟滚动参数计算 ---
    const itemHeight = globalState.sizeMap[globalState.currentIconSize] + 80; // 图片 + 名称 + margin (增加高度以适应多行文本)
    const gridWidth = container.clientWidth;
    console.log('Grid Container ClientWidth:', gridWidth);
    if (gridWidth === 0) return; 

    // 计算列数 (缩略图宽度 + gap 5px)
    const columns = Math.floor(gridWidth / (globalState.sizeMap[globalState.currentIconSize] + 2)); 
    console.log('Grid Container columns:', columns);
    if (columns === 0) return;
    
    // 使用完整的文件列表（API已经返回了当前页的数据）
    const allFiles = globalState.virtualFiles;
    
    const rowHeight = itemHeight;
    const totalRows = Math.ceil(allFiles.length / columns);
    
    // 设置虚拟高度
    grid.style.height = totalRows * rowHeight + 'px';

    // 清除所有子元素以进行全量刷新（用于尺寸切换）
    if (grid.children.length > 0) {
        while(grid.firstChild) {
            grid.removeChild(grid.firstChild);
        }
    }

    // 重新渲染当前可见项目
    console.log(globalState.virtualFiles.length);
    renderVisibleItems(true); 
    
    // 添加分页控件
    addPaginationControls(resultsContainer);
}

// 添加分页控件
function addPaginationControls(resultsContainer) {
    // 移除现有的分页控件
    const existingPagination = document.getElementById('pagination-controls');
    if (existingPagination) {
        existingPagination.remove();
    }
    
    // 使用 globalState 中的总页数，而不是自己计算
    const totalPages = globalState.pagination.totalPages;
    
    
    // 创建分页控件
    const paginationDiv = document.createElement('div');
    paginationDiv.id = 'pagination-controls';
    paginationDiv.className = 'pagination-controls d-flex justify-content-center align-items-center gap-1 mt-3';
    
    paginationDiv.innerHTML = `
        <div class="page-size-selector">
            <select id="page-size-select" class="form-select form-select-sm mx-0" style="width: auto;">
                <option value="50" ${globalState.pagination.pageSize === 50 ? 'selected' : ''}>50</option>
                <option value="100" ${globalState.pagination.pageSize === 100 ? 'selected' : ''}>100</option>
                <option value="200" ${globalState.pagination.pageSize === 200 ? 'selected' : ''}>200</option>
                <option value="500" ${globalState.pagination.pageSize === 500 ? 'selected' : ''}>500</option>
                <option value="1000" ${globalState.pagination.pageSize === 1000 ? 'selected' : ''}>1000</option>
            </select>
        </div>
        <nav>
            <ul class="pagination pagination-sm mb-0">
                <li class="page-item ${globalState.pagination.currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${globalState.pagination.currentPage - 1}">&lt;</a>
                </li>
                
                ${Array.from({length: Math.min(5, totalPages)}, (_, i) => {
                    const pageNum = Math.max(1, Math.min(globalState.pagination.currentPage - 2, totalPages - 4)) + i;
                    if (pageNum <= totalPages) {
                        return `
                            <li class="page-item ${globalState.pagination.currentPage === pageNum ? 'active' : ''}">
                                <a class="page-link" href="#" data-page="${pageNum}">${pageNum}</a>
                            </li>
                        `;
                    }
                    return '';
                }).join('')}
                
                <li class="page-item ${globalState.pagination.currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${globalState.pagination.currentPage + 1}">&gt;</a>
                </li>
            </ul>
        </nav>
        <div class="page-info">
            共 ${totalPages} 页
        </div>
    `;
    
    resultsContainer.appendChild(paginationDiv);
    
    // 绑定每页显示数量选择事件
    const pageSizeSelect = paginationDiv.querySelector('#page-size-select');
    pageSizeSelect.addEventListener('change', async (e) => {
        globalState.pagination.pageSize = parseInt(e.target.value);
        await saveUISettings();
        globalState.pagination.currentPage = 1; // 重置到第一页
        
        // 重新执行搜索以获取新页面大小的数据
        const query = document.getElementById('search-input').value;
        if (query.trim()) {
            // 显示加载状态
            const resultsContainer = document.getElementById('results-container');
            resultsContainer.innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>加载中...</p>
                </div>
            `;
            
            try {
                // 调用后端API获取指定页面和页面大小的数据
                const response = await apiSearchFiles({
                    tagExpression: query,
                    specialTagsStatus: globalState.specialTagsStatus,
                    sort_key: globalState.currentSortKey,
                    sort_order: globalState.currentSortOrder,
                    page: 1, // 总是获取第一页
                    page_size: globalState.pagination.pageSize,
                });
                
                // 更新分页状态
                globalState.pagination.currentPage = response.data.pagination.page;
                globalState.pagination.totalPages = response.data.pagination.pages;
                globalState.pagination.totalItems = response.data.pagination.total;
                globalState.pagination.pageSize = response.data.pagination.page_size;
                
                // 更新文件列表
                globalState.virtualFiles = response.data.file_paths.map(filePath => {
                    const fileName = filePath.split('\\').pop().split('/').pop();
                    return { 
                        filePath, 
                        fileName
                    };
                });
                
                // 重新渲染网格
                setupVirtualGrid();
            } catch (error) {
                console.error('更改每页数量失败:', error);
                resultsContainer.innerHTML = `
                    <div class="text-center text-danger py-5">
                        <i class="fa fa-exclamation-circle fa-3x mb-3"></i>
                        <p>加载失败，请重试</p>
                    </div>
                `;
            }
        }
    });
    
    // 绑定分页按钮事件
    paginationDiv.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', async (e) => {
            e.preventDefault();
            const targetPage = parseInt(e.target.getAttribute('data-page'));
            
            // 使用 globalState 中的总页数进行验证
            if (!isNaN(targetPage) && targetPage >= 1 && targetPage <= globalState.pagination.totalPages) {
                globalState.pagination.currentPage = targetPage;
                
                // 触发新的查询获取该页数据
                const query = document.getElementById('search-input').value;
                if (query.trim()) {
                    // 显示加载状态
                    const resultsContainer = document.getElementById('results-container');
                    resultsContainer.innerHTML = `
                        <div class="loading">
                            <div class="spinner"></div>
                            <p>加载中...</p>
                        </div>
                    `;
                    
                    try {
                        // 调用后端API获取指定页面的数据
                        const response = await apiSearchFiles({
                            tagExpression: query,
                            specialTagsStatus: globalState.specialTagsStatus,
                            sort_key: globalState.currentSortKey,
                            sort_order: globalState.currentSortOrder,
                            page: targetPage,
                            page_size: globalState.pagination.pageSize,
                        });
                        
                        // 更新分页状态
                        globalState.pagination.currentPage = response.data.pagination.page;
                        globalState.pagination.totalPages = response.data.pagination.pages;
                        globalState.pagination.totalItems = response.data.pagination.total;
                        globalState.pagination.pageSize = response.data.pagination.page_size;
                        
                        // 更新文件列表
                        globalState.virtualFiles = response.data.file_paths.map(filePath => {
                            const fileName = filePath.split('\\').pop().split('/').pop();
                            return { 
                                filePath, 
                                fileName
                            };
                        });
                        
                        // 重新渲染网格
                        setupVirtualGrid();
                    } catch (error) {
                        console.error('获取分页数据失败:', error);
                        resultsContainer.innerHTML = `
                            <div class="text-center text-danger py-5">
                                <i class="fa fa-exclamation-circle fa-3x mb-3"></i>
                                <p>加载失败，请重试</p>
                            </div>
                        `;
                    }
                }
            }
        });
    });
}

function renderVisibleItems(forceRefresh = false) {
    const container = document.getElementById('virtual-container');
    const grid = document.getElementById('virtual-grid');
    if (!container || !grid) return;

    const scrollTop = container.scrollTop;
    const clientHeight = container.clientHeight;
    
    const itemHeight = globalState.sizeMap[globalState.currentIconSize] + 80; // 图片 + 名称 + margin (增加高度以适应多行文本)
    const gridWidth = container.clientWidth;
    if (gridWidth === 0) return;

    const columns = Math.floor(gridWidth / (globalState.sizeMap[globalState.currentIconSize] + 2));
    if (columns === 0) return; 

    // 使用完整的文件列表（API已经返回了当前页的数据）
    const allFiles = globalState.virtualFiles;
    
    const rowHeight = itemHeight;
    const totalRows = Math.ceil(allFiles.length / columns);
    
    // 缓冲设置：增加可视区域上下的缓冲行数
    const BUFFER_ROWS = 4; 
    
    const startRow = Math.floor(scrollTop / rowHeight);
    const endRow = Math.min(startRow + Math.ceil(clientHeight / rowHeight) + BUFFER_ROWS, totalRows); 
    const startIndex = Math.max(0, (startRow - BUFFER_ROWS) * columns);
    const endIndex = Math.min(allFiles.length, endRow * columns);

    const newRenderedIndexes = new Set();
    const itemsToKeep = new Set();

    // 1. 渲染/更新新的可见项目
    for (let index = startIndex; index < endIndex; index++) {
        if (index >= allFiles.length) break;
        newRenderedIndexes.add(index);
        itemsToKeep.add(`item-${index}`); 

        let item = document.getElementById(`item-${index}`);
        
        if (!item || forceRefresh) { // 如果项目不存在 或 强制刷新 (如切换尺寸)
            // 如果项目不存在，则创建并添加
            const file = allFiles[index];
            const currentThumbSize = globalState.sizeMap[globalState.currentIconSize];
            const thumbSrc = apiGetThumbnail(file.filePath, currentThumbSize);
            if (!item) {
                item = document.createElement('div');
                item.id = `item-${index}`; // 设置ID以便追踪
                
                // 根据文件名长度动态计算行数，最多3行
                const fileName = file.fileName;
                const estimatedLines = Math.min(Math.ceil(fileName.length / 15), 3); // 每行大约15个字符
                
                item.innerHTML = `
                    <div class="thumb-img" style="background-image: url('${thumbSrc}')"></div>
                    <div class="thumb-name" style="display: -webkit-box; -webkit-line-clamp: ${estimatedLines}; -webkit-box-orient: vertical; overflow: hidden;" title="${file.fileName}">${file.fileName}</div>
                `;
                
                // 绑定点击事件
                item.addEventListener('click', async () => {
                    // 检测是否为文件夹
                    if (await isDirectory(file.filePath)) {
                        // 显示加载状态
                        const resultsContainer = document.getElementById('results-container');
                        resultsContainer.innerHTML = `
                            <div class="loading">
                                <div class="spinner"></div>
                                <p>加载文件夹内容...</p>
                            </div>
                        `;
                        
                        try {
                            // 获取文件夹内容
                            const folderContents = await getFolderContents(file.filePath);
                            
                            if (folderContents.length > 0) {
                                // 更新文件列表为文件夹内容
                                globalState.virtualFiles = folderContents.map(filePath => {
                                    const fileName = filePath.split('\\').pop().split('/').pop();
                                    return { 
                                        filePath, 
                                        fileName
                                    };
                                });
                                
                                // 更新分页状态（文件夹内容不分页）
                                globalState.pagination.currentPage = 1;
                                globalState.pagination.totalPages = 1;
                                globalState.pagination.totalItems = folderContents.length;
                                
                                // 添加文件夹路径到历史堆栈
                                if (!globalState.folderHistory) {
                                    globalState.folderHistory = [];
                                }
                                globalState.folderHistory.push(file.filePath);
                                
                                // 重新渲染网格
                                setupVirtualGrid();
                            } else {
                                resultsContainer.innerHTML = `
                                    <div class="text-center text-muted py-5">
                                        <i class="fa fa-folder-open-o fa-3x mb-3"></i>
                                        <p>文件夹为空</p>
                                    </div>
                                `;
                            }
                        } catch (error) {
                            console.error('加载文件夹内容失败:', error);
                            resultsContainer.innerHTML = `
                                <div class="text-center text-danger py-5">
                                    <i class="fa fa-exclamation-circle fa-3x mb-3"></i>
                                    <p>加载文件夹内容失败</p>
                                </div>
                            `;
                        }
                    } else {
                        // 检测是否为音频文件
                        if (isAudioFile(file.filePath)) {
                            // 从当前文件列表中筛选出所有音频文件
                            const audioFiles = allFiles
                                .filter(f => isAudioFile(f.filePath))
                                .map(f => f.filePath);

                            // 找到当前文件在音频列表中的索引
                            const currentIndex = audioFiles.indexOf(file.filePath);

                            // 跳转到音频播放器页面
                            const playlistParam = encodeURIComponent(JSON.stringify(audioFiles));
                            window.location.href = `/audio_player?playlist=${playlistParam}&index=${currentIndex}`;
                        } else {
                            // 非音频文件，使用原有逻辑直接打开
                            const targetUrl = apiOpenFile(file.filePath);
                            window.open(targetUrl);
                        }
                    }
                });
                
                grid.appendChild(item);
            } else {
                item.querySelector('.thumb-img').style.backgroundImage = `url('${thumbSrc}')`;
                // 更新文件名显示
                const fileName = allFiles[index].fileName;
                const estimatedLines = Math.min(Math.ceil(fileName.length / 15), 3); // 每行大约15个字符
                const nameElement = item.querySelector('.thumb-name');
                nameElement.style.webkitLineClamp = estimatedLines;
                nameElement.title = fileName;
                nameElement.textContent = fileName;
            }
            
            // 刷新样式和位置
            const row = Math.floor(index / columns);
            const col = index % columns;
            
            item.className = `thumb-item fade-in ${globalState.currentIconSize}`; // 确保应用当前尺寸
            item.style.position = 'absolute';
            item.style.top = row * rowHeight + 'px';
            // 计算列位置，考虑 gap
            const itemWidth = globalState.sizeMap[globalState.currentIconSize];
            const gap = (gridWidth - columns * itemWidth) / (columns - 1);
            const calculatedGap = isFinite(gap) && gap > 0 ? gap : 15; // 确保 gap 有效
            item.style.left = col * (itemWidth + calculatedGap) + 'px';
            item.style.width = itemWidth + 'px';

        } else {
            // 如果项目已存在，仅更新位置 (可选，优化性能)
            const row = Math.floor(index / columns);
            const col = index % columns;
            const itemWidth = globalState.sizeMap[globalState.currentIconSize];
            const gap = (gridWidth - columns * itemWidth) / (columns - 1);
            const calculatedGap = isFinite(gap) && gap > 0 ? gap : 15;
            item.style.top = row * rowHeight + 'px';
            item.style.left = col * (itemWidth + calculatedGap) + 'px';
        }
    }

    // 2. 移除不再可见的项目 (除非是强制刷新，通常在尺寸切换时不移除)
    if (!forceRefresh) {
        // 获取所有当前网格中的项目
        const currentItems = Array.from(grid.children);
        
        for (const item of currentItems) {
            const itemId = item.id;
            const itemIndex = parseInt(itemId.replace('item-', ''));
            
            // 如果项目索引超出当前文件列表范围，则移除
            if (itemIndex >= allFiles.length || !newRenderedIndexes.has(itemIndex)) {
                grid.removeChild(item);
            }
        }
    }


    // 3. 更新已渲染索引
    globalState.renderedIndexes = newRenderedIndexes;
}