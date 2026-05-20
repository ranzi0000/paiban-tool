"""导出 PDF：用 QPainter + QPdfWriter 把场景渲染到 A4 PDF"""
from PyQt6.QtCore import QSizeF, QMarginsF, Qt
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter

from canvas import CanvasScene


def export_scene_to_pdf(scene: CanvasScene, out_path: str, orient: str = 'landscape'):
    """把场景按 A4 满版渲染到 PDF。
    用 QPrinter（HighResolution 模式 = 1200 DPI）+ QPainter，文字保持矢量。"""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(out_path)
    layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Landscape if orient == 'landscape' else QPageLayout.Orientation.Portrait,
        QMarginsF(0, 0, 0, 0),
        QPageLayout.Unit.Millimeter,
    )
    printer.setPageLayout(layout)

    # 导出时隐藏文字框的辅助边框：
    #  - _export_mode=True 让 paint() 跳过虚线框/选中橙框/缩放手柄
    #  - 同时取消选中，避免 QGraphicsTextItem 自带的选中虚线进 PDF
    selected_backup = []
    box_items = scene.box_items()
    for it in box_items:
        if it.isSelected():
            selected_backup.append(it)
            it.setSelected(False)
        it._export_mode = True

    painter = QPainter(printer)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    # 关键：painter 在 HighResolution (1200 DPI) 下用 device pixel 坐标系
    # 必须用 painter.viewport() 取整页 device pixel 区域，不能用 Unit.Point
    # （之前用 Unit.Point 导致 scene 只渲染到 ~24% 区域）
    target_rect = painter.viewport()
    from PyQt6.QtCore import QRectF
    scene.render(painter, QRectF(target_rect), scene.sceneRect())
    painter.end()

    # 恢复状态
    for it in box_items:
        it._export_mode = False
    for it in selected_backup:
        it.setSelected(True)
