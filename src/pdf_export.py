"""导出 PDF：用 QPainter + QPdfWriter 把场景渲染到 A4 PDF"""
from PyQt6.QtCore import QSizeF, QMarginsF, Qt
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter

from canvas import CanvasScene, TextBoxItem


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

    # 临时隐藏文字框的虚线/选中边（painter 渲染时通过 painter.setPen 已不影响）
    # QGraphicsTextItem 的 isSelected() 状态会让 paint 画选中框 → 临时取消选中
    selected_backup = []
    for it in scene.text_items():
        if it.isSelected():
            selected_backup.append(it)
            it.setSelected(False)

    painter = QPainter(printer)
    # 渲染整个 scene 到 printer 的 pageRect
    target_rect = printer.pageRect(QPrinter.Unit.Point)
    # 用 sceneRect 做 source
    scene.render(painter, target_rect, scene.sceneRect())
    painter.end()

    # 恢复选中状态
    for it in selected_backup:
        it.setSelected(True)
