# 排版小工具

一个本地运行的桌面排版工具：**载入底图 → 拖出文字框 / 照片框 → 编辑 → 导出 PDF**。

适合做"在固定底图上填字"的批量场景：祈福牌位、请柬模板、奖状证书、产品标签等。所有数据在本地处理，不上传任何服务器。

![screenshot](docs/screenshot.png)

## 为什么不用浏览器

之前做过 HTML 版本（`web/` 目录留有备份），但浏览器的 FontFace API 对字体格式校验过于严格，**很多中文手写字体（30MB+ CJK .ttf）会被拒绝**，提示 `Invalid font data in ArrayBuffer`。Qt 的字体引擎基于 FreeType，宽容得多，能直接吃下浏览器拒绝的字体——这是桌面化的核心动机。

## 核心功能

- **加载任意图片当背景**（PNG / JPG / WebP / TIFF 等），支持**直接把图片拖进窗口**
- **A4 横向/竖向自适应**，背景图按比例居中铺满
- **拖出任意数量的文字框**，每个独立设置：
  - 横排 / **竖排**（真竖排：字正立、从上往下、列从右往左）
  - 字体（系统已装 + 用户导入的字体）
  - 字号 / 粗体 / 斜体
  - 颜色 / 对齐 / 行高
  - 内容（支持多行 / 直接键盘输入）
- **照片框**：文字框可一键转为照片框并插入照片（完整保比例居中显示）
- **导入本地字体文件**（.ttf / .otf / .ttc / .woff / .woff2）
  - Qt 字体引擎宽容，**浏览器拒绝的字体在这里能加载**
  - 持久化到本地，重启自动加载
- **模板保存 / 加载**（含背景图 + 文字框 / 照片框位置 + 样式 + 内容）
- **导出 PDF**（1200 DPI 矢量渲染，文字保持可缩放）
- **窗口可自由缩放**，画布 / 面板间分隔条可拖
- **跨平台**：Windows / macOS / Linux 都能跑

## 安装与运行

### 普通用户（Windows）

直接到 [Releases](../../releases) 下载最新 `.exe`，双击运行。

### 开发者 / macOS / Linux

```bash
git clone https://github.com/<your-username>/paiban-tool.git
cd paiban-tool

# 装依赖
pip install -r requirements.txt

# 运行
cd src && python main.py
```

依赖（详见 `requirements.txt`）：
- Python 3.10+
- PyQt6

## 使用流程

1. 点"选择图片…"选底图，或**直接把图片拖进窗口**
2. 在画布上**按住鼠标拖**画文字框 — **拖出来直接进入编辑模式**，立刻可打字
3. **单击**选中文字框 → 右侧改字体 / 横竖排 / 字号 / 颜色 / 对齐
4. 想放照片：选中文字框 → 右侧"插入照片…" → 该框变成照片框
5. 点右下 **"导出 PDF"** 保存
6. 调好的版面可保存为**模板**，下次复用（含字段位置和样式）

### 键盘快捷键

选中文字框 / 照片框后：

| 快捷键 | 作用 |
|---|---|
| `Delete` / `Backspace` | 删除选中框 |
| `← → ↑ ↓` | 微移 1 像素 |
| `Shift + ← → ↑ ↓` | 微移 10 像素 |
| `Ctrl + D` | 复制选中框（位置 +12px） |
| `Esc` | 取消选中 |
| `Ctrl + 滚轮` | 缩放画布 |

字号 spinbox 选中后可直接键盘输入数字。

### 字体导入

如果你想用系统外的手写体 / 设计字体：
1. 右侧"导入字体"区点 **+ 选字体文件**
2. 选 `.ttf` / `.otf` 等字体文件
3. 字体加入下拉，立即可选

## 自己打包成 EXE

项目里 `.github/workflows/build-windows.yml` 已配置好。**推一个 `v*` 标签**触发自动打包：

```bash
git tag v0.1.0
git push origin v0.1.0
```

打包好的 `.exe` 会自动发布到 GitHub Releases。

手动打包（本地）：

```bash
cd src
pip install pyinstaller
pyinstaller --onefile --windowed --name 排版小工具 --collect-all PyQt6 main.py
# 输出在 src/dist/
```

## 项目结构

```
paiban-tool/
├── src/
│   ├── main.py             # 入口
│   ├── main_window.py      # 主窗口
│   ├── canvas.py           # 画布 + 文字框(横/竖排) + 照片框（QGraphicsView）
│   ├── side_panel.py       # 右侧属性面板
│   ├── font_manager.py     # 字体管理
│   ├── template_store.py   # 模板保存/加载
│   ├── pdf_export.py       # PDF 导出
│   └── style.py            # QSS 样式
├── .github/workflows/
│   └── build-windows.yml   # 自动打包 Windows EXE
├── requirements.txt
└── README.md
```

## 数据存放位置

- **导入字体**：`~/.paiban-tool/paiban-tool/fonts/`（macOS/Linux）/ `%APPDATA%\paiban-tool\fonts\`（Windows）
- **模板文件**：同上目录的 `templates/` 子目录

## 已知限制

- 文字框的字号当前用 `pt`（点），打印时 1pt ≈ 0.353mm。如果你需要按 mm 精确控制可以等比换算
- PDF 导出按场景 1:1 渲染，文字保持矢量；背景图按嵌入分辨率
- 当前只支持单页 A4，多页文档不支持

## 许可

MIT
