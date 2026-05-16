"""画布：背景图 + 可编辑文字框（基于 QGraphicsView/Scene）"""
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItemGroup,
)
from PyQt6.QtGui import (
    QPixmap, QPen, QColor, QBrush, QFont, QPainter, QTransform, QCursor,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject

# A4 在 96 DPI 屏幕下的像素尺寸（用于场景坐标系）
MM_TO_PX = 96 / 25.4   # ~3.78
A4_LANDSCAPE = (297 * MM_TO_PX, 210 * MM_TO_PX)
A4_PORTRAIT  = (210 * MM_TO_PX, 297 * MM_TO_PX)


class TextBoxItem(QGraphicsTextItem):
    """可拖动、可编辑、带缩放手柄的文字框"""
    HANDLE_SIZE = 12

    def __init__(self, scene_ref):
        super().__init__()
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

    # ------- 缩放手柄 -------
    def _handle_rect(self):
        br = self.boundingRect()
        s = self.HANDLE_SIZE
        return QRectF(br.right() - s, br.bottom() - s, s, s)

    def paint(self, painter, option, widget=None):
        # 选中时画橙色描边 + 缩放手柄；未选中时虚线蓝边
        super().paint(painter, option, widget)
        br = self.boundingRect()
        if self.isSelected():
            pen = QPen(QColor('#ff8800'), 1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)
            # 缩放手柄
            painter.fillRect(self._handle_rect(), QColor('#ff8800'))
        else:
            pen = QPen(QColor(21, 101, 192, 160), 0.8, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)

    def hoverMoveEvent(self, event):
        if self._handle_rect().contains(event.pos()):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        # 缩放手柄检测
        if event.button() == Qt.MouseButton.LeftButton and self._handle_rect().contains(event.pos()):
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
        # 双击进入编辑模式
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
        return t


class CanvasScene(QGraphicsScene):
    """画布场景：背景图 + 多个文字框 + 鼠标拖框新建"""
    selection_changed = pyqtSignal(object)   # 当前选中的 TextBoxItem 或 None

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
        # 满版拉伸到 sceneRect（A4）——分别按 x/y 缩放，确保图片占满整页
        sr = self.sceneRect()
        sx = sr.width()  / pixmap.width()
        sy = sr.height() / pixmap.height()
        from PyQt6.QtGui import QTransform
        item.setTransform(QTransform.fromScale(sx, sy))
        item.setPos(0, 0)
        item.setZValue(-1000)
        self.addItem(item)
        self.bg_item = item

    def text_items(self):
        return [it for it in self.items() if isinstance(it, TextBoxItem)]

    def _on_selection(self):
        sel = self.selectedItems()
        cur = None
        for it in sel:
            if isinstance(it, TextBoxItem):
                cur = it; break
        self.selection_changed.emit(cur)

    # ------- 鼠标：在空白处拖出新文字框 -------
    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        # 文字框、文字框子元素（cursor / handle）→ 默认处理
        if isinstance(item, TextBoxItem):
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
            self._draw_start = None
            self._draw_rect_item = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CanvasView(QGraphicsView):
    """视图：负责显示场景、缩放适配窗口"""
    def __init__(self):
        super().__init__()
        self.setObjectName('canvasArea')
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
