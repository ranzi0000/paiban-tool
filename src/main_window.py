"""主窗口：组合画布 + 右侧面板"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QStatusBar, QSplitter,
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QTextOption
from PyQt6.QtCore import Qt, QPointF

from canvas import CanvasView, TextBoxItem, PhotoBoxItem, first_image_path
from side_panel import SidePanel
from font_manager import FontManager
from template_store import TemplateStore, pixmap_to_base64, pixmap_from_base64
from pdf_export import export_scene_to_pdf


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('排版小工具')
        self.resize(1280, 820)
        self.setAcceptDrops(True)

        self.font_manager = FontManager()
        self.template_store = TemplateStore()
        self._orient = 'landscape'
        self._current_image_path = None
        self._current_pixmap = None  # 保留原始 pixmap 用于保存模板

        # 主体：画布 | 可拖动分隔条 | 右侧面板（面板自带滚动区）
        self.canvas = CanvasView()
        self.side = SidePanel(self.font_manager, self.template_store)
        self.side.setMinimumWidth(280)
        self.side.setMaximumWidth(460)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.side)
        splitter.setStretchFactor(0, 1)   # 窗口变化时画布伸缩
        splitter.setStretchFactor(1, 0)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([920, 340])
        self.setCentralWidget(splitter)

        self.setMinimumSize(900, 600)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('就绪。点"选择图片…"开始')

        # 信号
        self.canvas.scene_.selection_changed.connect(self.side.bind_selection)
        self.canvas.image_dropped.connect(self.load_image_from_path)
        self.side.open_image.connect(self.open_image)
        self.side.orient_changed.connect(self.change_orient)
        self.side.save_template.connect(self.save_template)
        self.side.load_template.connect(self.load_template)
        self.side.delete_template.connect(self.delete_template)
        self.side.export_templates.connect(self.export_templates)
        self.side.import_templates.connect(self.import_templates)
        self.side.import_font.connect(self.import_font)
        self.side.remove_font.connect(self.remove_font)
        self.side.export_pdf.connect(self.export_pdf)
        self.side.text_changed.connect(self.on_box_action)

    # ================= 文件 =================
    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择图片', '',
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;All Files (*)')
        if not path: return
        self.load_image_from_path(path)

    def load_image_from_path(self, path):
        """加载一张图片为底图（文件对话框与拖放共用）"""
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, '错误', '无法加载图片：' + path); return
        self._current_image_path = path
        self._current_pixmap = pm
        # 自动判断方向
        orient = 'landscape' if pm.width() >= pm.height() else 'portrait'
        self.change_orient(orient)
        if orient == 'landscape':
            self.side.btn_landscape.setChecked(True)
        else:
            self.side.btn_portrait.setChecked(True)
        self.canvas.scene_.set_background_image(pm)
        self.canvas.fit_scene()
        self.statusBar().showMessage(f'已加载：{os.path.basename(path)}  {pm.width()}×{pm.height()}')

    # ------- 拖放图片到窗口 -------
    def dragEnterEvent(self, event):
        if first_image_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if first_image_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        p = first_image_path(event.mimeData())
        if p:
            self.load_image_from_path(p)
            event.acceptProposedAction()
        else:
            event.ignore()

    def change_orient(self, orient):
        self._orient = orient
        self.canvas.scene_.set_orientation(orient)
        if self._current_pixmap:
            self.canvas.scene_.set_background_image(self._current_pixmap)
        self.canvas.fit_scene()

    # ================= 字体 =================
    def import_font(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '导入字体', '',
            'Fonts (*.ttf *.otf *.ttc *.woff *.woff2)')
        if not paths: return
        ok, fail = 0, []
        for p in paths:
            success, info = self.font_manager.import_font(p)
            if success: ok += 1
            else: fail.append(f'{os.path.basename(p)}: {info}')
        self.side._refresh_imported_fonts_list()
        msg = f'导入完成：成功 {ok}'
        if fail: msg += '，失败 ' + str(len(fail)) + '：\n' + '\n'.join(fail)
        QMessageBox.information(self, '字体导入', msg)

    def remove_font(self, family):
        self.font_manager.remove_imported(family)
        self.statusBar().showMessage(f'已移除字体：{family}')

    # ================= 面板动作 =================
    def on_box_action(self, prop, val):
        sel = self.canvas.scene_.selectedItems()
        item = next((i for i in sel if isinstance(i, (TextBoxItem, PhotoBoxItem))), None)
        if not item: return
        if prop == 'delete':
            self.canvas.scene_.removeItem(item)
            return
        if prop == 'insert_photo':
            if isinstance(item, TextBoxItem):
                self._insert_photo(item)
            return
        if prop == 'change_photo':
            if isinstance(item, PhotoBoxItem):
                self._change_photo(item)
            return
        if prop == 'revert_to_text':
            if isinstance(item, PhotoBoxItem):
                self._revert_to_text(item)
            return
        # 以下都是文字框属性
        if not isinstance(item, TextBoxItem):
            return
        if prop == 'direction':
            item.set_direction(val)
            return
        if prop == 'line_height':
            item.set_line_height(val)
            return
        f = item.font()
        if prop == 'font_family':
            f.setFamily(val)
        elif prop == 'font_size':
            f.setPointSize(int(val))
        elif prop == 'font_bold':
            f.setBold(bool(val))
        elif prop == 'font_italic':
            f.setItalic(bool(val))
        elif prop == 'color':
            item.setDefaultTextColor(QColor(val))
        elif prop == 'align':
            opt = item.document().defaultTextOption()
            a = {'left': Qt.AlignmentFlag.AlignLeft,
                 'center': Qt.AlignmentFlag.AlignHCenter,
                 'right': Qt.AlignmentFlag.AlignRight}[val]
            opt.setAlignment(a)
            item.document().setDefaultTextOption(opt)
        item.setFont(f)
        item.update()

    # ------- 文字框 ↔ 照片框 转换 -------
    def _insert_photo(self, text_item):
        path, _ = QFileDialog.getOpenFileName(self, '选择照片', '',
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)')
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, '错误', '无法加载照片：' + path)
            return
        # 用文字框的位置与宽度，按照片比例算出高度 → 照片初始无留白
        pos = text_item.pos()
        w = max(60.0, text_item.boundingRect().width())
        h = w * pm.height() / pm.width()
        self.canvas.scene_.removeItem(text_item)
        p = PhotoBoxItem(self.canvas.scene_, w, h)
        p.setPos(pos)
        p.set_pixmap(pm)
        self.canvas.scene_.addItem(p)
        p.setSelected(True)
        self.statusBar().showMessage('已插入照片，可拖动 / 拖右下角缩放')

    def _change_photo(self, photo_item):
        path, _ = QFileDialog.getOpenFileName(self, '选择照片', '',
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)')
        if not path:
            return
        if not photo_item.set_image_path(path):
            QMessageBox.warning(self, '错误', '无法加载照片：' + path)

    def _revert_to_text(self, photo_item):
        pos = photo_item.pos()
        w = max(60.0, photo_item.boundingRect().width())
        self.canvas.scene_.removeItem(photo_item)
        t = TextBoxItem(self.canvas.scene_)
        t.setPos(pos)
        t.set_fixed_width(w)
        self.canvas.scene_.addItem(t)
        t.setSelected(True)

    # ================= 模板 =================
    def save_template(self, name):
        if not self._current_pixmap:
            QMessageBox.warning(self, '提示', '请先加载图片')
            return
        data = {
            'orient': self._orient,
            'bg_image_base64': pixmap_to_base64(self._current_pixmap),
            'boxes': [b.to_dict() for b in self.canvas.scene_.box_items()],
        }
        self.template_store.save(name, data)
        self.statusBar().showMessage(f'模板"{name}"已保存')
        self.side._refresh_template_list()

    def load_template(self, path: Path):
        data = self.template_store.load(path)
        # 清当前
        for it in self.canvas.scene_.box_items():
            self.canvas.scene_.removeItem(it)
        self._orient = data.get('orient', 'landscape')
        self.canvas.scene_.set_orientation(self._orient)
        if self._orient == 'landscape': self.side.btn_landscape.setChecked(True)
        else: self.side.btn_portrait.setChecked(True)
        # 背景图
        if 'bg_image_base64' in data:
            pm = pixmap_from_base64(data['bg_image_base64'])
            self._current_pixmap = pm
            self.canvas.scene_.set_background_image(pm)
        # 文字框 / 照片框（老模板无 type 字段 → 默认按文字框读）
        for bd in data.get('boxes', []):
            if bd.get('type') == 'photo':
                b = PhotoBoxItem.from_dict(bd, self.canvas.scene_)
            else:
                b = TextBoxItem.from_dict(bd, self.canvas.scene_)
            self.canvas.scene_.addItem(b)
        self.canvas.fit_scene()
        self.side.tpl_name_input.setText(data.get('name', ''))
        self.statusBar().showMessage(f'已加载模板：{data.get("name")}')

    def delete_template(self, path):
        self.template_store.delete(path)
        self.statusBar().showMessage('已删除模板')

    def export_templates(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出模板', '排版模板_备份.json', 'JSON (*.json)')
        if not path: return
        self.template_store.export_all(path)
        QMessageBox.information(self, '成功', f'已导出到：{path}')

    def import_templates(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入模板', '', 'JSON (*.json)')
        if not path: return
        try:
            n = self.template_store.import_bundle(path)
            QMessageBox.information(self, '成功', f'已导入 {n} 个模板')
            self.side._refresh_template_list()
        except Exception as e:
            QMessageBox.warning(self, '导入失败', str(e))

    # ================= PDF 导出 =================
    def export_pdf(self):
        if not self._current_pixmap:
            QMessageBox.warning(self, '提示', '请先加载图片'); return
        default_name = (self.side.tpl_name_input.text().strip() or 'paiban') + '.pdf'
        path, _ = QFileDialog.getSaveFileName(self, '导出 PDF', default_name, 'PDF (*.pdf)')
        if not path: return
        try:
            export_scene_to_pdf(self.canvas.scene_, path, self._orient)
            self.statusBar().showMessage(f'已导出：{path}')
            QMessageBox.information(self, '完成', f'PDF 已保存：\n{path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', str(e))
