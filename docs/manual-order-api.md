# 手工排序 HTTP 接口

桌面程序启动后，Web 服务提供以下三个接口，本机默认地址为 `http://127.0.0.1:10252`。接口使用 JSON 请求体，并显式指定标签库 `db_path`，不会切换桌面或 Web 当前选中的标签库。

| 接口（均为 POST） | 用途 | 请求字段 | 未入库路径的处理 |
| --- | --- | --- | --- |
| `/api/manual_order/query` | 查询给定文件的手工顺序 | `db_path`、`file_paths` | 忽略并列入 `missing_file_paths` |
| `/api/manual_order/move` | 将一组文件移到目标前面或后面 | `db_path`、`file_paths`、`target`、`placement` | 任一待移动文件或目标未入库，整次请求返回 404 |
| `/api/manual_order/set` | 将 N 个文件按数组顺序放回它们原来占用的位置 | `db_path`、`file_paths` | 忽略并列入 `missing_file_paths`，只重排已有文件 |

文件列表必须是非空数组，不能重复；路径支持 `/` 和 `\`，返回路径使用 `/`。查询和设置会忽略未入库的路径；移动接口要求所有路径属于指定标签库。排序在整个标签库中生效，真实文件内容和修改时间保持不变。

“未入库”以指定标签库中是否存在文件记录为准；文件存在于磁盘上，也可能尚未入库。宽松处理仅针对未入库路径，空数组、空路径、重复路径和无效参数仍返回 400，标签库不存在仍返回 404。

## 登录与会话

先通过 `POST /login` 提交表单字段 `username`、`password`，成功后沿用响应设置的会话 Cookie 调用接口。用户名和密码使用 Web 登录页的账户信息，登录请求使用表单，排序请求使用 JSON。

外部脚本需要自行登录并保存 Cookie；浏览器已经登录，不会让独立脚本自动获得会话。登录和接口调用应使用同一个主机地址，例如统一使用 `127.0.0.1`。未携带有效会话时，三个接口均返回 HTTP 401：

```json
{"success": false, "error": "unauthorized", "message": "请先登录"}
```

## 查询顺序

假设 A、B、C 已入库，当前手工顺序为 A、B、C，`missing.jpg` 未入库。发送到 `/api/manual_order/query`：

```json
{
  "db_path": "D:/data/photos.db",
  "file_paths": ["D:/photos/C.jpg", "D:/photos/missing.jpg", "D:/photos/A.jpg", "D:/photos/B.jpg"]
}
```

返回 HTTP 200，`file_paths` 仅包含已入库文件，并按手工顺序排列：

```json
{
  "success": true,
  "file_paths": ["D:/photos/A.jpg", "D:/photos/B.jpg", "D:/photos/C.jpg"],
  "missing_file_paths": ["D:/photos/missing.jpg"]
}
```

未入库的路径按请求顺序列在 `missing_file_paths` 中，不影响其他文件的查询。如果所有路径都未入库，仍返回 HTTP 200，`file_paths` 为空数组，`missing_file_paths` 包含全部请求路径。

```json
{
  "success": true,
  "file_paths": [],
  "missing_file_paths": ["D:/photos/missing.jpg"]
}
```

## 移动一组文件

发送到 `/api/manual_order/move`：

```json
{
  "db_path": "D:/data/photos.db",
  "file_paths": ["D:/photos/C.jpg", "D:/photos/D.jpg"],
  "target": "D:/photos/B.jpg",
  "placement": "before"
}
```

`placement` 为 `before` 或 `after`，组内顺序采用 `file_paths` 的顺序。目标位置根据完整标签库中的相邻文件计算，包括当前筛选隐藏的文件。目标属于移动组，或该组已经位于目标指定的一侧且顺序一致时，返回无操作结果。

任一待移动文件或 `target` 未入库时，整次请求返回 HTTP 404、`error: "file_not_found"`，原顺序保持不变。此接口使用严格校验，成功响应不包含 `missing_file_paths`。

## 设置 N 个文件的顺序

发送到 `/api/manual_order/set`：

```json
{
  "db_path": "D:/data/photos.db",
  "file_paths": ["D:/photos/C.jpg", "D:/photos/missing.jpg", "D:/photos/A.jpg", "D:/photos/B.jpg"]
}
```

例如全库原顺序为 `A → X → B → Y → C`，忽略未入库的 `missing.jpg` 后，按 `[C, A, B]` 设置顺序，结果为 `C → X → A → Y → B`。未提交文件保持原来的全库位置。传入全库文件时，数组就是全库的最终顺序。

成功响应示例（HTTP 200）：

```json
{
  "success": true,
  "changed": true,
  "affected_count": 3,
  "missing_file_paths": ["D:/photos/missing.jpg"]
}
```

未入库的路径在同一写事务中被过滤，只重排库中已有的文件。例如提交 `[C, 未入库文件, A, B]`，实际按 `[C, A, B]` 设置顺序。响应额外包含 `missing_file_paths`，按请求顺序列出被忽略的路径。全部路径都未入库，或过滤后排列没有变化时，返回 HTTP 200、`changed: false`、`affected_count: 0`，不新增文件记录或发送通知。

例如仅提交未入库的 `missing.jpg`：

```json
{
  "success": true,
  "changed": false,
  "affected_count": 0,
  "missing_file_paths": ["D:/photos/missing.jpg"]
}
```

通常复用所选文件的原排序值；排序值相同且需要调整次序时，只调整涉及的等值段。其他文件的位置保持不变，新文件仍以入库时的修改时间参与排序。

## 保存结果和错误

移动和设置接口均返回 `success`、`changed` 和 `affected_count`：

```json
{"success": true, "changed": true, "affected_count": 3}
```

设置接口还返回 `missing_file_paths`，没有缺失路径时为 `[]`。

`affected_count` 是实际修改排序值的文件数量，等值段调整可能涉及未提交的文件。无操作时 `changed` 为 `false`，数量为 `0`。有效写入使用单次事务，提交后发布一次通知；桌面主窗口处于手工模式时原地重排，保留选区、当前文件和滚动位置。

错误也返回 JSON，例如：

```json
{"success": false, "error": "file_not_found", "message": "文件已不在当前标签库中"}
```

| HTTP 状态 | `error` | 含义 |
| --- | --- | --- |
| 400 | `invalid_request` | 请求格式、参数或重复路径有误 |
| 401 | `unauthorized` | 尚未登录 |
| 404 | `tagbase_not_found` | 指定标签库不存在，三个接口均适用 |
| 404 | `file_not_found` | 移动接口引用的文件或目标未入库 |
| 500 | `database_error` | 数据库操作失败；写事务会回滚 |

## Python 调用示例

以下示例使用 `requests`，替换用户名、密码、标签库和文件路径即可。`Session` 自动保存登录 Cookie，供后续查询、移动、设置请求使用。

```python
import requests

base_url = "http://127.0.0.1:10252"
client = requests.Session()
login = client.post(
    f"{base_url}/login",
    data={"username": "你的用户名", "password": "你的密码"},
    allow_redirects=False,
    timeout=10,
)
if login.status_code != 302:
    raise RuntimeError("登录失败，请检查用户名和密码")

response = client.post(
    f"{base_url}/api/manual_order/set",
    json={
        "db_path": "D:/data/photos.db",
        "file_paths": [
            "D:/photos/C.jpg",
            "D:/photos/missing.jpg",
            "D:/photos/A.jpg",
            "D:/photos/B.jpg",
        ],
    },
    timeout=10,
)
response.raise_for_status()
result = response.json()
print("顺序是否改变：", result["changed"])
print("忽略的未入库路径：", result["missing_file_paths"])
```
