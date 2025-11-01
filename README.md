Qt应用打包：PyInstaller --name Tag2File --windowed --onefile main.py
Web应用需要将tag2file.html中的API_BASE_URL修改为自己的IP



## 🚀 运行指南 (Run Instructions)

本项目包含一个基于 Qt 的桌面后端应用 (`Tag2File.exe`) 和一个 Web 前端界面 (`tag2file.html`)。

请按照以下步骤启动应用：

### 步骤 1: 启动后端服务

1.  **运行后端程序：** 双击执行 `Tag2File.exe`。
2.  **检查端口：** 确保后端服务成功启动，并在默认端口 `10252` 监听。
3.  **获取 IP 地址 (关键):** * 在运行 `Tag2File.exe` 的这台电脑上，打开命令提示符 (CMD) 或 PowerShell。
    * 输入命令 `ipconfig`，找到你的 Wi-Fi 或以太网适配器下的 **IPv4 地址**（例如：`192.168.1.5`）。
    * **记住这个 IP 地址，这是其他设备用来访问你的服务的地址。**

> ⚠️ **注意防火墙：** 如果您是首次运行，Windows 防火墙可能会阻止连接。请确保您允许应用程序访问私有网络。

### 步骤 2: 配置 Web 前端

由于前端和后端需要在局域网内通信，您需要手动修改前端 HTML 文件中的 IP 地址。

1.  用任意文本编辑器（如 VS Code, Notepad++）打开 `tag2file.html` 文件。
2.  找到以下代码行：
    ```javascript
    // 后端服务地址 - 请替换为您的Windows电脑IP
    const API_BASE_URL = '[http://192.168.0.102:10252](http://192.168.0.102:10252)'; 
    ```
3.  将 `192.168.0.102` **替换**为您在 **步骤 1** 中获取的 IPv4 地址。
    * **示例：** 如果 IP 是 `192.168.1.5`，则修改为 `const API_BASE_URL = 'http://192.168.1.5:10252';`

### 步骤 3: 访问应用

完成配置后：

* 在同一台电脑上：用浏览器打开修改后的 `tag2file.html` 文件。
* 在局域网内其他设备上 (如手机)：在浏览器中输入**运行后端服务设备的 IP 地址**，然后加上文件路径。
    * **示例：** `http://192.168.1.5/tag2file.html` (如果文件是通过一个简易 Web Server 提供的) 或直接通过局域网共享访问。

---
### 💡 附加建议

这种解决方案清晰且直接，避免了使用复杂的配置系统。如果你希望提高用户体验，也可以在 `tag2file.html` 的头部添加一个醒目的 **配置提醒**，引导用户参考 `README`。

Would you like me to draft a quick **配置提醒**的 HTML 注释，你可以加到 `tag2file.html` 文件的 `<head>` 部分？
