"""UI 样式（QSS）"""

APP_QSS = """
QMainWindow, QWidget {
    background: #f4f4f0;
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: #1a1a1a;
}

QSplitter::handle { background: #d0d0c8; }
QSplitter::handle:horizontal { width: 6px; }
QSplitter::handle:horizontal:hover { background: #b8b8b0; }

/* 左侧画布灰底 */
#canvasArea { background: #555; }
#canvasArea QScrollBar:vertical, #canvasArea QScrollBar:horizontal { background: #444; }

/* 右侧面板 */
#sidePanel, #sideContent { background: #f8f8f5; }
#sideFooter {
    background: #f8f8f5;
    border-top: 1px solid #d0d0c8;
}
#sidePanel QLabel.section-title {
    font-weight: 600;
    font-size: 13px;
    color: #333;
    padding-top: 6px;
}
#sidePanel QLabel.field-label {
    color: #666;
    font-size: 12px;
    padding-top: 4px;
}

QPushButton {
    background: #1a1a1a;
    color: #fff;
    border: none;
    padding: 7px 14px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 18px;
}
QPushButton:hover { background: #333; }
QPushButton:pressed { background: #000; }
QPushButton:disabled { background: #999; color: #ddd; }

QPushButton[role="primary"] {
    background: #c01e1e;
    font-weight: 600;
    padding: 10px 14px;
}
QPushButton[role="primary"]:hover { background: #a01818; }

QPushButton[role="secondary"] {
    background: #e0e0d8;
    color: #1a1a1a;
}
QPushButton[role="secondary"]:hover { background: #d0d0c8; }

QPushButton[role="danger"] { background: #c00; }
QPushButton[role="danger"]:hover { background: #a00; }

QPushButton[role="toggle"] {
    background: #ebebe5;
    color: #333;
    padding: 6px 10px;
}
QPushButton[role="toggle"]:checked {
    background: #1a1a1a;
    color: #fff;
}

QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #fff;
    border: 1px solid #d0d0c8;
    border-radius: 3px;
    padding: 4px 7px;
    font-size: 13px;
    selection-background-color: #c01e1e;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #c01e1e;
}

QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #fff;
    border: 1px solid #d0d0c8;
    selection-background-color: #c01e1e;
    selection-color: #fff;
}

QListWidget {
    background: #fff;
    border: 1px solid #e0e0d8;
    border-radius: 3px;
    padding: 2px;
}
QListWidget::item { padding: 6px 8px; border-radius: 2px; }
QListWidget::item:selected { background: #fff8e1; color: #1a1a1a; border: 1px solid #ff8800; }
QListWidget::item:hover { background: #fafafa; }

QStatusBar {
    background: #fff;
    color: #666;
    border-top: 1px solid #d0d0c8;
}

QMenuBar { background: #f4f4f0; color: #1a1a1a; }
QMenuBar::item:selected { background: #d0d0c8; }
QMenu { background: #fff; border: 1px solid #c0c0b8; }
QMenu::item:selected { background: #c01e1e; color: #fff; }

QScrollArea { border: none; }
QToolTip {
    background: #1a1a1a;
    color: #fff;
    border: none;
    padding: 4px 8px;
}
"""
