import { globalState } from '../state.js';
import { extractDbName } from '../utils.js';
import { apiGetInit, apiSwitchDatabase, } from '../api.js';
import { loadAvailableTags } from './tagExpression.js';
import { clearSearch } from './search.js';


// 加载可用标签库列表
export function loadDatabaseList() {
    const dbListMenu = document.getElementById('db-list-menu');
    const currentDBNameElements = document.querySelectorAll('#current-db-name');
    
    dbListMenu.innerHTML = '<li class="dropdown-item text-muted">加载中...</li>';

    // 1. 调用 /get_init 路由
    apiGetInit()
    .then(response => {
        const dbList = response.data.database_list;
        const activeDbPath = response.data.database_path;

        // 2. 存储在前端
        globalState.availableDatabases = dbList;
        globalState.currentDatabasePath = activeDbPath;
        
        if (!dbList || dbList.length === 0) {
            dbListMenu.innerHTML = '<li class="dropdown-item text-muted">无可用标签库</li>';
            currentDBNameElements.forEach(el => el.textContent = '无标签库');
        } else {
            dbListMenu.innerHTML = ''; // 清空列表
            
            // 3. 循环完整路径列表, *构建* 菜单
            dbList.forEach(dbPath => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.className = 'dropdown-item'; // 初始无 active
                a.href = '#';
                a.textContent = extractDbName(dbPath); // 显示短名称
                a.setAttribute('data-db-path', dbPath); // 存储完整路径
                
                // 绑定切换事件
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    switchDatabase(dbPath);
                });
                
                li.appendChild(a);
                dbListMenu.appendChild(li);
            });
            
            // 4. 调用UI更新函数来设置初始 'active' 状态
            updateDatabaseUI(activeDbPath);
        }
        
        // 5. 成功后加载标签树
        loadAvailableTags();
    })
    .catch(error => {
        console.error('Failed to load database list:', error);
        dbListMenu.innerHTML = '<li class="dropdown-item text-danger">加载失败</li>';
        currentDBNameElements.forEach(el => el.textContent = '加载失败');
    });
}

function updateDatabaseUI(activeDbPath) {
    // 1. 更新所有显示当前DB名称的元素
    const currentDBNameElements = document.querySelectorAll('#current-db-name');
    currentDBNameElements.forEach(el => el.textContent = extractDbName(activeDbPath));
    
    // 2. 更新下拉列表中的 'active' 状态
    const dbListMenu = document.getElementById('db-list-menu');
    dbListMenu.querySelectorAll('a.dropdown-item').forEach(a => {
        if (a.getAttribute('data-db-path') === activeDbPath) {
            a.classList.add('active');
        } else {
            a.classList.remove('active');
        }
    });
}

// 切换数据库
function switchDatabase(dbPath) {
    // 1. 用 globalState.currentDatabasePath (完整路径) 检查
    if (dbPath === globalState.currentDatabasePath) {
        return;
    }
    
    const currentDBNameElements = document.querySelectorAll('#current-db-name');
    const oldDbPath = globalState.currentDatabasePath; // 2. 存储旧的 *路径*
    
    // 3. 立即更新UI为 "切换中..."
    globalState.currentDatabasePath = dbPath; // 乐观地设置新路径
    currentDBNameElements.forEach(el => el.textContent = '切换中...');
    
    // 4. POST请求发送完整路径
    apiSwitchDatabase(dbPath)
    .then(response => {
        if (response.data.success) {
            // 切换成功
            // 5. globalState.currentDatabasePath 已被设置为新路径
            // 6. 更新UI (active 状态和按钮文本)
            updateDatabaseUI(dbPath);
            // 7. 重新加载新数据库的标签树
            loadAvailableTags(); 
            // 8. 清空搜索结果
            clearSearch();
        } else {
            // 切换失败
            console.error('Switch DB failed:', response.data.message);
            alert(`切换标签库失败: ${response.data.message}`);
            // 9. 恢复旧路径并更新UI
            globalState.currentDatabasePath = oldDbPath; 
            updateDatabaseUI(oldDbPath);
        }
    })
    .catch(error => {
        // 切换失败
        console.error('Switch DB failed:', error);
        alert('切换标签库失败，请检查服务器连接');
        // 10. 恢复旧路径并更新UI
        globalState.currentDatabasePath = oldDbPath;
        updateDatabaseUI(oldDbPath);
    });
}

