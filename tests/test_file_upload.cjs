// Run with: node --experimental-vm-modules --test tests/test_file_upload.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function harness(upload) {
    const elements = Object.fromEntries(['upload-files-btn', 'upload-files-input', 'upload-status'].map(id => [id, {
        listeners: {}, disabled: false, textContent: '', value: '', files: [],
        addEventListener(event, handler) { this.listeners[event] = handler; },
        click() { this.clicked = true; },
    }]));
    const state = { browseMode: 'folder_browse', currentFolder: 'D:/target' };
    const refreshes = [];
    const context = vm.createContext({ document: { getElementById: id => elements[id] } });
    const dependencies = {
        '../api.js': { apiUploadFile: upload },
        '../state.js': { globalState: state },
        './virtualGrid.js': { loadFolderContents: async (...args) => refreshes.push(args) },
    };
    const source = fs.readFileSync(path.join(__dirname, '../web_app/frontend/static/js/features/fileUpload.js'), 'utf8');
    const module = new vm.SourceTextModule(source, { context });
    await module.link(specifier => new vm.SyntheticModule(Object.keys(dependencies[specifier]), function () {
        for (const [key, value] of Object.entries(dependencies[specifier])) this.setExport(key, value);
    }, { context }));
    await module.evaluate();
    module.namespace.setupFileUpload();
    const button = elements['upload-files-btn'];
    const input = elements['upload-files-input'];
    const status = elements['upload-status'];
    return { state, refreshes, button, input, status, async choose(files) {
        button.listeners.click();
        input.files = files;
        await input.listeners.change();
    } };
}

test('multiple files report partial failure, keep uploading, and refresh destination', async () => {
    const uploaded = [];
    const h = await harness(async ({ file, folderPath, onUploadProgress }) => {
        uploaded.push([file.name, folderPath]);
        onUploadProgress({ loaded: 5, total: 10 });
        assert.match(h.status.textContent, /50%/);
        assert.equal(h.button.disabled, true);
        if (file.name === 'duplicate.txt') throw { response: { status: 409, data: { message: '同名文件已存在' } } };
    });
    await h.choose([{ name: '中文.txt' }, { name: 'duplicate.txt' }, { name: 'last.txt' }]);
    assert.equal(uploaded.length, 3);
    assert.equal(h.refreshes.length, 1);
    assert.equal(h.refreshes[0][0], 'D:/target');
    assert.equal(h.refreshes[0][1].preserveRoot, true);
    assert.match(h.status.textContent, /2\/3/);
    assert.match(h.status.textContent, /duplicate.txt：同名文件已存在/);
    assert.equal(h.button.disabled, false);
    assert.equal(h.input.value, '');
});

test('navigation during upload retains captured destination without navigating back', async () => {
    const destinations = [];
    const h = await harness(async ({ folderPath }) => {
        destinations.push(folderPath);
        h.state.currentFolder = 'D:/elsewhere';
    });
    await h.choose([{ name: 'one.txt' }, { name: 'two.txt' }]);
    assert.deepEqual(destinations, ['D:/target', 'D:/target']);
    assert.equal(h.refreshes.length, 0);
    assert.equal(h.state.currentFolder, 'D:/elsewhere');
});

test('cancel does nothing and the same file can be retried after network failure', async () => {
    let calls = 0;
    const h = await harness(async () => { if (++calls === 1) throw new Error('network'); });
    await h.choose([]);
    assert.equal(calls, 0);
    await h.choose([{ name: 'retry.txt' }]);
    assert.match(h.status.textContent, /连接中断/);
    assert.equal(h.button.disabled, false);
    await h.choose([{ name: 'retry.txt' }]);
    assert.equal(calls, 2);
    assert.match(h.status.textContent, /1\/1/);
    assert.equal(h.status.className, 'alert alert-success');
});

test('expired login stops the queue and explains unuploaded files', async () => {
    let calls = 0;
    const h = await harness(async () => {
        calls++;
        throw { response: { status: 401, data: { message: '请先登录' } } };
    });
    await h.choose([{ name: 'one.txt' }, { name: 'two.txt' }]);
    assert.equal(calls, 1);
    assert.match(h.status.textContent, /请先登录/);
    assert.match(h.status.textContent, /2 个文件未确认上传成功/);
    assert.equal(h.button.disabled, false);
});
