"""画布：背景图 + 可编辑文字框（基于 QGraphicsView/Scene）"""
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItemGroup, QInputDialog,
    QFileDialog,
)
from PyQt6.QtGui import (
    QPixmap, QPen, QColor, QBrush, QFont, QPainter, QTransform, QCursor,
    QFontMetricsF, QTextCursor, QTextCharFormat,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject

from template_store import pixmap_to_base64, pixmap_from_base64

# A4 在 96 DPI 屏幕下的像素尺寸（用于场景坐标系）
MM_TO_PX = 96 / 25.4   # ~3.78
A4_LANDSCAPE = (297 * MM_TO_PX, 210 * MM_TO_PX)
A4_PORTRAIT  = (210 * MM_TO_PX, 297 * MM_TO_PX)

IMG_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff', '.webp')


def first_image_path(mime):
    """从拖放 mimeData 里取第一个本地图片文件路径，没有则返回 None"""
    if not mime.hasUrls():
        return None
    for url in mime.urls():
        if url.isLocalFile():
            p = url.toLocalFile()
            if p.lower().endswith(IMG_EXTS):
                return p
    return None


class TextBoxItem(QGraphicsTextItem):
    """可拖动、可编辑、带缩放手柄的文字框"""
    HANDLE_SIZE = 12

    def __init__(self, scene_ref):
        super().__init__()
        self._direction = 'horizontal'   # 'horizontal' | 'vertical'
        self._export_mode = False        # 导出 PDF 时置真，paint 跳过辅助边框
        self._scene_ref = scene_ref
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setPlainText('双击编辑')
        self.setFont(QFont('Songti SC', 18))
        self.setDefaultTextColor(QColor('#000000'))
        self._fixed_width = 200.0   # 强制宽度（让换行符合用户预期）
        self.setTextWidth(self._fixed_width)
        self._resizing = False
        self._resize_anchor = QPointF()
        self._orig_width = 200.0

    def set_fixed_width(self, w):
        self._fixed_width = max(20.0, w)
        self.setTextWidth(self._fixed_width)

    # ------- 排版方向（横排 / 竖排）-------
    def set_direction(self, d):
        if d not in ('horizontal', 'vertical') or d == self._direction:
            return
        self.prepareGeometryChange()
        self._direction = d
        if d == 'vertical':
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self._resizing = False
        self.update()

    def setFont(self, font):
        # QGraphicsTextItem.setFont 只改 defaultFont；已有字符的 QTextCharFormat
        # 优先级更高，不会被覆盖 → "字号没办法放大缩小" 的根因
        # 必须用 cursor.mergeCharFormat 强制刷新整篇文档
        self.prepareGeometryChange()
        super().setFont(font)
        self._apply_charformat(font=font)

    def setPlainText(self, text):
        self.prepareGeometryChange()
        super().setPlainText(text)
        self._apply_charformat(font=self.font(), color=self.defaultTextColor())

    def setDefaultTextColor(self, color):
        # 同 setFont：默认色会被已有字符的 charFormat 覆盖，必须强刷
        super().setDefaultTextColor(color)
        self._apply_charformat(color=color)

    def _apply_charformat(self, font=None, color=None):
        """把指定属性强制 merge 到整篇文档 + 当前光标 charFormat。"""
        if font is None and color is None:
            return
        fmt = QTextCharFormat()
        if font is not None:
            fmt.setFont(font)
        if color is not None:
            fmt.setForeground(color)
        # 全文 merge
        doc_cur = QTextCursor(self.document())
        doc_cur.beginEditBlock()
        doc_cur.select(QTextCursor.SelectionType.Document)
        doc_cur.mergeCharFormat(fmt)
        doc_cur.endEditBlock()
        # 同步编辑光标，使后续键盘输入也用新格式
        tc = self.textCursor()
        tc.mergeCharFormat(fmt)
        self.setTextCursor(tc)

    def set_line_height(self, mult):
        from PyQt6.QtGui import QTextBlockFormat
        self.prepareGeometryChange()
        c = QTextCursor(self.document())
        c.select(QTextCursor.SelectionType.Document)
        bf = QTextBlockFormat()
        bf.setLineHeight(float(mult) * 100, 1)  # 1 = ProportionalHeight
        c.mergeBlockFormat(bf)
        self.update()

    # ------- 竖排几何与绘制 -------
    def _vertical_metrics(self):
        """返回 (字体度量, 字高, 行进步长, 列宽)"""
        fm = QFontMetricsF(self.font())
        cell = fm.height()
        mult = (self._line_height_pct() or 100) / 100.0
        if mult <= 0:
            mult = 1.0
        return fm, cell, cell * mult, cell

    def _vertical_bounding_rect(self):
        fm, cell, cell_h, col_w = self._vertical_metrics()
        cols = self.toPlainText().split('\n')
        n_cols = max(1, len(cols))
        max_chars = max([len(c) for c in cols] + [1])
        return QRectF(0, 0, n_cols * col_w, max_chars * cell_h)

    def _paint_vertical(self, painter):
        fm, cell, cell_h, col_w = self._vertical_metrics()
        cols = self.toPlainText().split('\n')
        n_cols = len(cols)
        painter.save()
        painter.setFont(self.font())
        painter.setPen(QPen(self.defaultTextColor()))
        for ci, col in enumerate(cols):
            # 第 0 列在最右，新列往左排（传统右起）
            x = (n_cols - 1 - ci) * col_w
            for ri, ch in enumerate(col):
                adv = fm.horizontalAdvance(ch)
                cx = x + (col_w - adv) / 2.0
                baseline = ri * cell_h + (cell_h - cell) / 2.0 + fm.ascent()
                painter.drawText(QPointF(cx, baseline), ch)
        painter.restore()

    def boundingRect(self):
        if self._direction == 'vertical':
            return self._vertical_bounding_rect()
        return super().boundingRect()

    def shape(self):
        if self._direction == 'vertical':
            from PyQt6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRect(self._vertical_bounding_rect())
            return path
        return super().shape()

    # ------- 缩放手柄 -------
    def _handle_rect(self):
        br = self.boundingRect()
        s = self.HANDLE_SIZE
        return QRectF(br.right() - s, br.bottom() - s, s, s)

    def paint(self, painter, option, widget=None):
        # 文字本体
        if self._direction == 'vertical':
            self._paint_vertical(painter)
        else:
            super().paint(painter, option, widget)
        # 导出/打印时不画任何辅助边框
        if self._export_mode:
            return
        # 选中时画橙色描边 + 缩放手柄（手柄仅横排）；未选中时虚线蓝边
        br = self.boundingRect()
        if self.isSelected():
            painter.setPen(QPen(QColor('#ff8800'), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)
            if self._direction == 'horizontal':
                painter.fillRect(self._handle_rect(), QColor('#ff8800'))
        else:
            painter.setPen(QPen(QColor(21, 101, 192, 160), 0.8, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)

    def hoverMoveEvent(self, event):
        if self._direction == 'horizontal' and self._handle_rect().contains(event.pos()):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        # 缩放手柄检测（仅横排）
        if (self._direction == 'horizontal'
                and event.button() == Qt.MouseButton.LeftButton
                and self._handle_rect().contains(event.pos())):
            self._resizing = True
            self._resize_anchor = event.scenePos()
            self._orig_width = self._fixed_width
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos().x() - self._resize_anchor.x()
            self.set_fixed_width(self._orig_width + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 竖排：弹横排输入框编辑（Qt 无原生竖排编辑器）
        if self._direction == 'vertical':
            cur = self.toPlainText()
            if cur == '双击编辑':
                cur = ''
            text, ok = QInputDialog.getMultiLineText(
                None, '编辑竖排文字', '输入文字（回车换行 = 新起一列）：', cur)
            if ok:
                self.setPlainText(text if text.strip() else '双击编辑')
            event.accept()
            return
        # 横排：双击就地编辑
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        # 选中所有内容（首次双击时）
        if self.toPlainText() == '双击编辑':
            self.setPlainText('')
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if self.toPlainText() == '':
            self.setPlainText('双击编辑')
        super().focusOutEvent(event)

    def to_dict(self):
        """序列化（保存模板用）"""
        f = self.font()
        return {
            'type': 'text',
            'x': self.pos().x(),
            'y': self.pos().y(),
            'width': self._fixed_width,
            'text': self.toPlainText(),
            'font_family': f.family(),
            'font_size_pt': f.pointSize(),
            'font_bold': f.bold(),
            'font_italic': f.italic(),
            'color': self.defaultTextColor().name(),
            'align': int(self.document().defaultTextOption().alignment().value),
            'line_height': self._line_height_pct(),
            'direction': self._direction,
        }

    def _line_height_pct(self):
        block = self.document().begin()
        if block.isValid():
            return block.blockFormat().lineHeight() or 100
        return 100

    @classmethod
    def from_dict(cls, d, scene_ref):
        t = cls(scene_ref)
        t.setPos(d['x'], d['y'])
        t.set_fixed_width(d['width'])
        t.setPlainText(d['text'])
        f = QFont(d['font_family'], d['font_size_pt'])
        f.setBold(d.get('font_bold', False))
        f.setItalic(d.get('font_italic', False))
        t.setFont(f)
        t.setDefaultTextColor(QColor(d['color']))
        from PyQt6.QtGui import QTextOption
        opt = t.document().defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag(d.get('align', int(Qt.AlignmentFlag.AlignLeft.value))))
        t.document().setDefaultTextOption(opt)
        t.set_direction(d.get('direction', 'horizontal'))
        return t


class PhotoBoxItem(QGraphicsItem):
    """可拖动、可缩放的照片框；照片按 contain（完整保比例）居中显示"""
    HANDLE_SIZE = 12

    def __init__(self, scene_ref, w=200.0, h=150.0):
        super().__init__()
        self._scene_ref = scene_ref
        self._export_mode = False
        self._w = max(20.0, float(w))
        self._h = max(20.0, float(h))
        self._pixmap = QPixmap()          # 空 = 还没选照片
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._resizing = False
        self._resize_anchor = QPointF()
        self._orig_size = (self._w, self._h)

    # ------- 照片 / 尺寸 -------
    def set_pixmap(self, pixmap):
        self._pixmap = pixmap if (pixmap is not None and not pixmap.isNull()) else QPixmap()
        self.update()

    def set_image_path(self, path):
        pm = QPixmap(path)
        if pm.isNull():
            return False
        self._pixmap = pm
        self.update()
        return True

    def set_size(self, w, h):
        self.prepareGeometryChange()
        self._w = max(20.0, float(w))
        self._h = max(20.0, float(h))
        self.update()

    # ------- 几何 -------
    def boundingRect(self):
        return QRectF(0, 0, self._w, self._h)

    def _handle_rect(self):
        s = self.HANDLE_SIZE
        return QRectF(self._w - s, self._h - s, s, s)

    # ------- 绘制 -------
    def paint(self, painter, option, widget=None):
        r = self.boundingRect()
        if not self._pixmap.isNull():
            pm = self._pixmap
            # contain：按比例缩到能放进框的最大尺寸，居中
            s = min(self._w / pm.width(), self._h / pm.height())
            dw, dh = pm.width() * s, pm.height() * s
            dx = (self._w - dw) / 2.0
            dy = (self._h - dh) / 2.0
            painter.drawPixmap(QRectF(dx, dy, dw, dh), pm, QRectF(pm.rect()))
        else:
            painter.fillRect(r, QColor('#f0f0ec'))
            painter.setPen(QColor('#999999'))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, '双击插入照片')
        # 导出/打印时不画辅助边框
        if self._export_mode:
            return
        if self.isSelected():
            painter.setPen(QPen(QColor('#ff8800'), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
            painter.fillRect(self._handle_rect(), QColor('#ff8800'))
        else:
            painter.setPen(QPen(QColor(21, 101, 192, 160), 0.8, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

    # ------- 鼠标 -------
    def hoverMoveEvent(self, event):
        if self._handle_rect().contains(event.pos()):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._resize_anchor = event.scenePos()
            self._orig_size = (self._w, self._h)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            dx = event.scenePos().x() - self._resize_anchor.x()
            dy = event.scenePos().y() - self._resize_anchor.y()
            self.set_size(self._orig_size[0] + dx, self._orig_size[1] + dy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 双击 = 换照片
        path, _ = QFileDialog.getOpenFileName(
            None, '选择照片', '',
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)')
        if path:
            self.set_image_path(path)
        event.accept()

    # ------- 序列化 -------
    def to_dict(self):
        return {
            'type': 'photo',
            'x': self.pos().x(),
            'y': self.pos().y(),
            'width': self._w,
            'height': self._h,
            'image_base64': pixmap_to_base64(self._pixmap) if not self._pixmap.isNull() else '',
        }

    @classmethod
    def from_dict(cls, d, scene_ref):
        p = cls(scene_ref, d.get('width', 200.0), d.get('height', 150.0))
        p.setPos(d.get('x', 0), d.get('y', 0))
        b64 = d.get('image_base64', '')
        if b64:
            p.set_pixmap(pixmap_from_base64(b64))
        return p


class CanvasScene(QGraphicsScene):
    """画布场景：背景图 + 多个文字框/照片框 + 鼠标拖框新建"""
    selection_changed = pyqtSignal(object)   # 当前选中的 TextBoxItem / PhotoBoxItem 或 None

    def __init__(self):
        super().__init__()
        self.bg_item = None
        self._draw_start = None
        self._draw_rect_item = None
        self.set_orientation('landscape')
        self.selectionChanged.connect(self._on_selection)

    def set_orientation(self, orient):
        w, h = A4_LANDSCAPE if orient == 'landscape' else A4_PORTRAIT
        self.setSceneRect(0, 0, w, h)
        # 白色背景
        self.setBackgroundBrush(QBrush(QColor('#ffffff')))

    def set_background_image(self, pixmap: QPixmap):
        if self.bg_item:
            self.removeItem(self.bg_item)
            self.bg_item = None
        if pixmap.isNull():
            return
        item = QGraphicsPixmapItem(pixmap)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        # 保比例最大化（contain）：图按原比例缩到能容纳 A4 的最大尺寸，居中放置
        # 比例不匹配时会有上下/左右白边——这是用户预期的行为（不要拉伸变形）
        sr = self.sceneRect()
        sx = sr.width()  / pixmap.width()
        sy = sr.height() / pixmap.height()
        s = min(sx, sy)
        item.setScale(s)
        item.setPos((sr.width()  - pixmap.width()  * s) / 2,
                    (sr.height() - pixmap.height() * s) / 2)
        item.setZValue(-1000)
        self.addItem(item)
        self.bg_item = item

    def box_items(self):
        """所有文字框 + 照片框"""
        return [it for it in self.items()
                if isinstance(it, (TextBoxItem, PhotoBoxItem))]

    def _on_selection(self):
        sel = self.selectedItems()
        cur = None
        for it in sel:
            if isinstance(it, (TextBoxItem, PhotoBoxItem)):
                cur = it; break
        self.selection_changed.emit(cur)

    # ------- 鼠标：在空白处拖出新文字框 -------
    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        # 文字框 / 照片框 → 默认处理（选中、拖动、缩放）
        if isinstance(item, (TextBoxItem, PhotoBoxItem)):
            super().mousePressEvent(event)
            return
        # 背景图也不算
        if event.button() == Qt.MouseButton.LeftButton:
            self._draw_start = event.scenePos()
            self._draw_rect_item = None
            # 清除当前选中
            for it in self.selectedItems():
                it.setSelected(False)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._draw_start is not None:
            p1 = self._draw_start
            p2 = event.scenePos()
            r = QRectF(min(p1.x(), p2.x()), min(p1.y(), p2.y()),
                       abs(p2.x() - p1.x()), abs(p2.y() - p1.y()))
            if not self._draw_rect_item:
                self._draw_rect_item = self.addRect(
                    r, QPen(QColor(21, 101, 192), 1.2, Qt.PenStyle.DashLine),
                    QBrush(QColor(21, 101, 192, 30))
                )
                self._draw_rect_item.setZValue(1000)
            else:
                self._draw_rect_item.setRect(r)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._draw_start is not None:
            if self._draw_rect_item:
                r = self._draw_rect_item.rect()
                self.removeItem(self._draw_rect_item)
                if r.width() > 8 and r.height() > 8:
                    t = TextBoxItem(self)
                    t.setPos(r.topLeft())
                    t.set_fixed_width(r.width())
                    self.addItem(t)
                    t.setSelected(True)
                    # UX：拖出新框直接进入编辑模式，光标就绪可立即输入
                    t.setPlainText('')
                    t.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                    t.setFocus(Qt.FocusReason.MouseFocusReason)
            self._draw_start = None
            self._draw_rect_item = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CanvasView(QGraphicsView):
    """视图：负责显示场景、缩放适配窗口"""
    image_dropped = pyqtSignal(str)   # 拖入图片文件时发出，参数为本地路径

    def __init__(self):
        super().__init__()
        self.setObjectName('canvasArea')
        self.setAcceptDrops(True)
        self.scene_ = CanvasScene()
        self.setScene(self.scene_)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setBackgroundBrush(QBrush(QColor('#555')))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 接得到键盘焦点，否则 keyPressEvent（Delete / 方向键 / Ctrl+D）不会触发
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def fit_scene(self):
        self.fitInView(self.scene_.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_scene()

    def wheelEvent(self, event):
        # 缩放：Ctrl + 滚轮
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    # ------- 键盘快捷键 -------
    def _selected_boxes(self):
        return [it for it in self.scene_.selectedItems()
                if isinstance(it, (TextBoxItem, PhotoBoxItem))]

    def _editing_text(self):
        """是否有 TextBoxItem 正处于编辑模式（应让键盘事件走文字编辑）"""
        for it in self._selected_boxes():
            if isinstance(it, TextBoxItem) and \
                    it.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction:
                return True
        return False

    def keyPressEvent(self, event):
        # 编辑模式让 Qt 处理（输入文字、方向键移光标）
        if self._editing_text():
            super().keyPressEvent(event)
            return

        boxes = self._selected_boxes()
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        # macOS 兼容：Cmd 也算 ctrl
        meta = bool(mods & Qt.KeyboardModifier.MetaModifier)
        ctrl_or_cmd = ctrl or meta

        # Delete / Backspace 删除选中
        if boxes and key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for it in boxes:
                self.scene_.removeItem(it)
            event.accept()
            return

        # 方向键微移（Shift = 10px，否则 1px）
        arrow_delta = {
            Qt.Key.Key_Left:  (-1, 0),
            Qt.Key.Key_Right: ( 1, 0),
            Qt.Key.Key_Up:    ( 0,-1),
            Qt.Key.Key_Down:  ( 0, 1),
        }
        if boxes and key in arrow_delta:
            step = 10 if shift else 1
            dx, dy = arrow_delta[key]
            for it in boxes:
                it.setPos(it.pos().x() + dx*step, it.pos().y() + dy*step)
            event.accept()
            return

        # Ctrl+D 复制选中（位置 +12/+12）
        if boxes and ctrl_or_cmd and key == Qt.Key.Key_D:
            copies = []
            for it in boxes:
                if isinstance(it, TextBoxItem):
                    new_it = TextBoxItem.from_dict(it.to_dict(), self.scene_)
                elif isinstance(it, PhotoBoxItem):
                    new_it = PhotoBoxItem.from_dict(it.to_dict(), self.scene_)
                else:
                    continue
                new_it.setPos(it.pos().x() + 12, it.pos().y() + 12)
                self.scene_.addItem(new_it)
                copies.append(new_it)
            # 选中新副本，原选中取消，方便用户继续 Ctrl+D 连续复制成阵列
            for it in boxes:
                it.setSelected(False)
            for c in copies:
                c.setSelected(True)
            event.accept()
            return

        # Esc 退出编辑模式 / 取消选中
        if key == Qt.Key.Key_Escape:
            for it in boxes:
                it.setSelected(False)
            event.accept()
            return

        super().keyPressEvent(event)

    # ------- 拖放图片到画布 -------
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
            self.image_dropped.emit(p)
            event.acceptProposedAction()
        else:
            event.ignore()
