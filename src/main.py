"""排版小工具 — 入口"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QLocale

from main_window import MainWindow
from style import APP_QSS


def main():
    QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    app = QApplication(sys.argv)
    app.setApplicationName('排版小工具')
    app.setOrganizationName('paiban-tool')
    app.setStyleSheet(APP_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
