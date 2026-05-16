# 浏览器版（早期原型，已废弃）

这是项目最早的原型，直接打开 `index.html` 即可在浏览器里使用。

## 为什么废弃

浏览器的 `FontFace API` 对中文手写字体（尤其 30MB+ 完整版 CJK）兼容性差，
报 `Invalid font data in ArrayBuffer`，连 opentype.js 净化也救不了部分字体。

桌面版（PyQt6 Qt 字体引擎）解决了这个问题——保留此文件作历史参考。
