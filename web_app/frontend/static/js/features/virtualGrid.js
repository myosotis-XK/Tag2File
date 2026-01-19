import { globalState } from '../state.js';
import { apiGetThumbnail, apiOpenFile } from '../api.js';
import { throttle } from '../utils.js';
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
    const availableHeight = window.innerHeight - topOffset - 20; // 减去 20px 作为底部间距
    container.style.height = Math.max(400, availableHeight) + 'px'; // 设置最小高度 400px
    document.documentElement.style.setProperty('--thumb-size', globalState.sizeMap[globalState.currentIconSize] + 'px'); // 更新 CSS 变量
    
    // --- 虚拟滚动参数计算 ---
    const itemHeight = globalState.sizeMap[globalState.currentIconSize] + 40; // 图片 + 名称 + margin
    const gridWidth = container.clientWidth;
    console.log('Grid Container ClientWidth:', gridWidth);
    if (gridWidth === 0) return; 

    // 计算列数 (缩略图宽度 + gap 5px)
    const columns = Math.floor(gridWidth / (globalState.sizeMap[globalState.currentIconSize] + 2)); 
    console.log('Grid Container columns:', columns);
    if (columns === 0) return;
    
    const rowHeight = itemHeight;
    const totalRows = Math.ceil(globalState.virtualFiles.length / columns);
    
    // 设置虚拟高度
    grid.style.height = totalRows * rowHeight + 'px';

    // 清除所有子元素以进行全量刷新（用于尺寸切换）
    if (grid.children.length > 0) {
        while(grid.firstChild) {
            grid.removeChild(grid.firstChild);
        }
    }

    // 重新渲染当前可见项目
    renderVisibleItems(true); 
}


function renderVisibleItems(forceRefresh = false) {
    const container = document.getElementById('virtual-container');
    const grid = document.getElementById('virtual-grid');
    if (!container || !grid) return;

    const scrollTop = container.scrollTop;
    const clientHeight = container.clientHeight;
    
    const itemHeight = globalState.sizeMap[globalState.currentIconSize] + 40;
    const gridWidth = container.clientWidth;
    if (gridWidth === 0) return;

    const columns = Math.floor(gridWidth / (globalState.sizeMap[globalState.currentIconSize] + 2));
    if (columns === 0) return; 

    const rowHeight = itemHeight;
    const totalRows = Math.ceil(globalState.virtualFiles.length / columns);
    
    // 缓冲设置：增加可视区域上下的缓冲行数
    const BUFFER_ROWS = 4; 
    
    const startRow = Math.floor(scrollTop / rowHeight);
    const endRow = Math.min(startRow + Math.ceil(clientHeight / rowHeight) + BUFFER_ROWS, totalRows); 
    const startIndex = Math.max(0, (startRow - BUFFER_ROWS) * columns);
    const endIndex = Math.min(globalState.virtualFiles.length, endRow * columns);

    const newRenderedIndexes = new Set();
    const itemsToKeep = new Set();

    // 1. 渲染/更新新的可见项目
    for (let index = startIndex; index < endIndex; index++) {
        if (index >= globalState.virtualFiles.length) break;
        newRenderedIndexes.add(index);
        itemsToKeep.add(`item-${index}`); 

        let item = document.getElementById(`item-${index}`);
        
        if (!item || forceRefresh) { // 如果项目不存在 或 强制刷新 (如切换尺寸)
            // 如果项目不存在，则创建并添加
            const file = globalState.virtualFiles[index];
            const currentThumbSize = globalState.sizeMap[globalState.currentIconSize];
            const thumbSrc = apiGetThumbnail(file.filePath, currentThumbSize);
            if (!item) {
                item = document.createElement('div');
                item.id = `item-${index}`; // 设置ID以便追踪
                
                item.innerHTML = `
                    <div class="thumb-img" style="background-image: url('${thumbSrc}')"></div>
                    <div class="thumb-name" title="${file.fileName}">${file.fileName}</div>
                `;
                
                // 绑定点击事件
                item.addEventListener('click', () => {
                    // 使用后端服务地址 + 新的接口，将文件路径作为参数传递
                    const targetUrl = apiOpenFile(file.filePath);
                    window.open(targetUrl);
                });
                
                grid.appendChild(item);
            } else {
                item.querySelector('.thumb-img').style.backgroundImage = `url('${thumbSrc}')`;
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
        const itemsToRemove = Array.from(globalState.renderedIndexes).filter(index => !newRenderedIndexes.has(index));
        
        itemsToRemove.forEach(index => {
            const item = document.getElementById(`item-${index}`);
            if (item) {
                grid.removeChild(item);
            }
        });
    }


    // 3. 更新已渲染索引
    globalState.renderedIndexes = newRenderedIndexes;
}