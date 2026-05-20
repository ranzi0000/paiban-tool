"""右侧面板：模板、方向、字体导入、文字框样式属性"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QFrame, QColorDialog, QFileDialog, QInputDialog, QMessageBox,
    QButtonGroup, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from canvas import TextBoxItem, PhotoBoxItem


def make_section_title(text):
    lbl = QLabel(text)
    lbl.setProperty('class', 'section-title')
    lbl.setStyleSheet('font-weight:600; font-size:13px; color:#333; padding-top:6px;')
    return lbl


def make_field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet('color:#555; font-size:12px;')
    return lbl


def make_hr():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet('background:#e0e0d8; max-height:1px; border:none;')
    return line


class SidePanel(QWidget):
    # 信号
    open_image       = pyqtSignal()
    orient_changed   = pyqtSignal(str)
    save_template    = pyqtSignal(str)
    load_template    = pyqtSignal(object)
    delete_template  = pyqtSignal(object)
    export_templates = pyqtSignal()
    import_templates = pyqtSignal()
    import_font      = pyqtSignal()
    remove_font      = pyqtSignal(str)
    export_pdf       = pyqtSignal()
    # 样式变更（属性面板）
    text_changed = pyqtSignal(str, object)   # prop_name, value

    def __init__(self, font_manager, template_store):
        super().__init__()
        self.setObjectName('sidePanel')
        self.font_manager = font_manager
        self.template_store = template_store
        self._current_item = None
        self._building = False   # 防止 signal 回环
        self._init_ui()
        self._refresh_template_list()
        self._refresh_imported_fonts_list()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 可滚动的内容区（窗口变矮时面板内部滚动，不撑大窗口）
        content = QWidget()
        content.setObjectName('sideContent')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # ===== 1. 图片 + 方向 =====
        layout.addWidget(make_section_title('图片与方向'))
        row = QHBoxLayout()
        btn_open = QPushButton('选择图片…')
        btn_open.clicked.connect(self.open_image.emit)
        row.addWidget(btn_open)
        layout.addLayout(row)

        row = QHBoxLayout()
        self.btn_landscape = QPushButton('横向 A4'); self.btn_landscape.setProperty('role','toggle'); self.btn_landscape.setCheckable(True); self.btn_landscape.setChecked(True)
        self.btn_portrait  = QPushButton('竖向 A4'); self.btn_portrait.setProperty('role','toggle');  self.btn_portrait.setCheckable(True)
        grp = QButtonGroup(self); grp.setExclusive(True); grp.addButton(self.btn_landscape); grp.addButton(self.btn_portrait)
        self.btn_landscape.clicked.connect(lambda: self.orient_changed.emit('landscape'))
        self.btn_portrait.clicked.connect(lambda: self.orient_changed.emit('portrait'))
        row.addWidget(self.btn_landscape); row.addWidget(self.btn_portrait)
        layout.addLayout(row)

        layout.addWidget(make_hr())

        # ===== 2. 模板 =====
        layout.addWidget(make_section_title('模板'))
        row = QHBoxLayout()
        self.tpl_name_input = QLineEdit(); self.tpl_name_input.setPlaceholderText('模板名（保存用）')
        btn_save = QPushButton('保存模板'); btn_save.clicked.connect(self._on_save_tpl)
        row.addWidget(self.tpl_name_input); row.addWidget(btn_save)
        layout.addLayout(row)

        self.tpl_list = QListWidget()
        self.tpl_list.setMaximumHeight(120)
        self.tpl_list.itemDoubleClicked.connect(self._on_load_tpl)
        layout.addWidget(self.tpl_list)

        row = QHBoxLayout()
        btn_load   = QPushButton('加载'); btn_load.setProperty('role','secondary'); btn_load.clicked.connect(self._on_load_tpl_clicked)
        btn_delete = QPushButton('删除'); btn_delete.setProperty('role','danger');    btn_delete.clicked.connect(self._on_delete_tpl)
        btn_export = QPushButton('导出'); btn_export.setProperty('role','secondary'); btn_export.clicked.connect(self.export_templates.emit)
        btn_import = QPushButton('导入'); btn_import.setProperty('role','secondary'); btn_import.clicked.connect(self.import_templates.emit)
        for b in (btn_load, btn_delete, btn_export, btn_import): row.addWidget(b)
        layout.addLayout(row)

        layout.addWidget(make_hr())

        # ===== 3. 字体导入 =====
        layout.addWidget(make_section_title('导入字体'))
        row = QHBoxLayout()
        btn_imp_font = QPushButton('+ 选字体文件'); btn_imp_font.clicked.connect(self.import_font.emit)
        row.addWidget(btn_imp_font)
        layout.addLayout(row)
        self.imp_font_list = QListWidget()
        self.imp_font_list.setMaximumHeight(80)
        self.imp_font_list.itemDoubleClicked.connect(self._on_remove_font)
        layout.addWidget(self.imp_font_list)
        hint = QLabel('双击列表项可移除已导入的字体。')
        hint.setStyleSheet('color:#888; font-size:11px;'); hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addWidget(make_hr())

        # ===== 4. 文字框 / 照片框属性（选中时显示）=====
        self.style_title = make_section_title('文字框样式')
        layout.addWidget(self.style_title)
        self.props_widget = QWidget()
        form = QFormLayout(self.props_widget)
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # 方向
        dir_row = QHBoxLayout(); dir_row.setSpacing(4)
        self.btn_dir_h = QPushButton('横排'); self.btn_dir_h.setProperty('role','toggle'); self.btn_dir_h.setCheckable(True); self.btn_dir_h.setChecked(True)
        self.btn_dir_v = QPushButton('竖排'); self.btn_dir_v.setProperty('role','toggle'); self.btn_dir_v.setCheckable(True)
        dir_grp = QButtonGroup(self); dir_grp.setExclusive(True); dir_grp.addButton(self.btn_dir_h); dir_grp.addButton(self.btn_dir_v)
        self.btn_dir_h.clicked.connect(lambda: self._on_direction_clicked('horizontal'))
        self.btn_dir_v.clicked.connect(lambda: self._on_direction_clicked('vertical'))
        dir_row.addWidget(self.btn_dir_h); dir_row.addWidget(self.btn_dir_v); dir_row.addStretch()
        form.addRow(make_field_label('方向'), dir_row)

        # 字体
        self.font_combo = QComboBox()
        self.font_combo.setMaxVisibleItems(20)
        # 用 currentIndexChanged + itemData 取真实 family（不是带 ★ 前缀的 displayText）
        self.font_combo.currentIndexChanged.connect(
            lambda i: self._emit('font_family', self.font_combo.itemData(i)) if i >= 0 else None
        )
        form.addRow(make_field_label('字体'), self.font_combo)

        # 字号
        size_row = QHBoxLayout(); size_row.setSpacing(4)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(4, 300)
        self.size_spin.setValue(18)
        self.size_spin.setSingleStep(2)  # 上下箭头每次 +/- 2，变化更明显
        self.size_spin.setSuffix(' pt')
        self.size_spin.valueChanged.connect(lambda v: self._emit('font_size', v))
        btn_minus = QPushButton('−'); btn_minus.setProperty('role','secondary'); btn_minus.setFixedWidth(34)
        btn_plus  = QPushButton('+'); btn_plus.setProperty('role','secondary');  btn_plus.setFixedWidth(34)
        btn_minus.clicked.connect(lambda: self.size_spin.setValue(self.size_spin.value() - 2))
        btn_plus.clicked.connect(lambda:  self.size_spin.setValue(self.size_spin.value() + 2))
        size_row.addWidget(btn_minus); size_row.addWidget(self.size_spin, 1); size_row.addWidget(btn_plus)
        form.addRow(make_field_label('字号'), size_row)

        # 样式
        style_row = QHBoxLayout(); style_row.setSpacing(4)
        self.btn_bold = QPushButton('B'); self.btn_bold.setProperty('role','toggle'); self.btn_bold.setCheckable(True); self.btn_bold.setFixedWidth(40)
        self.btn_italic = QPushButton('I'); self.btn_italic.setProperty('role','toggle'); self.btn_italic.setCheckable(True); self.btn_italic.setFixedWidth(40)
        self.btn_bold.clicked.connect(lambda: self._emit('font_bold', self.btn_bold.isChecked()))
        self.btn_italic.clicked.connect(lambda: self._emit('font_italic', self.btn_italic.isChecked()))
        style_row.addWidget(self.btn_bold); style_row.addWidget(self.btn_italic); style_row.addStretch()
        form.addRow(make_field_label('样式'), style_row)

        # 对齐
        align_row = QHBoxLayout(); align_row.setSpacing(4)
        self.btn_align_l = QPushButton('左'); self.btn_align_l.setProperty('role','toggle'); self.btn_align_l.setCheckable(True); self.btn_align_l.setChecked(True); self.btn_align_l.setFixedWidth(40)
        self.btn_align_c = QPushButton('中'); self.btn_align_c.setProperty('role','toggle'); self.btn_align_c.setCheckable(True); self.btn_align_c.setFixedWidth(40)
        self.btn_align_r = QPushButton('右'); self.btn_align_r.setProperty('role','toggle'); self.btn_align_r.setCheckable(True); self.btn_align_r.setFixedWidth(40)
        align_grp = QButtonGroup(self); align_grp.setExclusive(True)
        for b in (self.btn_align_l, self.btn_align_c, self.btn_align_r): align_grp.addButton(b); align_row.addWidget(b)
        align_row.addStretch()
        self.btn_align_l.clicked.connect(lambda: self._emit('align', 'left'))
        self.btn_align_c.clicked.connect(lambda: self._emit('align', 'center'))
        self.btn_align_r.clicked.connect(lambda: self._emit('align', 'right'))
        form.addRow(make_field_label('对齐'), align_row)

        # 字色
        self.btn_color = QPushButton('#000000')
        self.btn_color.clicked.connect(self._pick_color)
        form.addRow(make_field_label('字色'), self.btn_color)

        # 行高
        self.line_spin = QDoubleSpinBox(); self.line_spin.setRange(0.8, 3.0); self.line_spin.setSingleStep(0.05); self.line_spin.setValue(1.25)
        self.line_spin.setSuffix(' ×')
        self.line_spin.valueChanged.connect(lambda v: self._emit('line_height', v))
        form.addRow(make_field_label('行高'), self.line_spin)

        # 操作（占整行）
        form.addRow(make_hr())
        btn_to_photo = QPushButton('插入照片…'); btn_to_photo.setProperty('role','secondary')
        btn_to_photo.clicked.connect(lambda: self._emit('insert_photo', True))
        form.addRow(btn_to_photo)
        btn_del = QPushButton('删除文字框'); btn_del.setProperty('role','danger')
        btn_del.clicked.connect(lambda: self._emit('delete', True))
        form.addRow(btn_del)
        layout.addWidget(self.props_widget)
        self.props_widget.setEnabled(False)

        # 照片框属性（选中照片框时显示，替换上面的文字面板）
        self.photo_widget = QWidget()
        plv2 = QVBoxLayout(self.photo_widget); plv2.setContentsMargins(0,0,0,0); plv2.setSpacing(4)
        hint_p = QLabel('双击照片框可换图。照片完整保比例显示，框内可能留白。')
        hint_p.setStyleSheet('color:#888; font-size:11px;'); hint_p.setWordWrap(True)
        plv2.addWidget(hint_p)
        btn_change = QPushButton('换照片…')
        btn_change.clicked.connect(lambda: self._emit('change_photo', True))
        plv2.addWidget(btn_change)
        btn_revert = QPushButton('改回文字框'); btn_revert.setProperty('role','secondary')
        btn_revert.clicked.connect(lambda: self._emit('revert_to_text', True))
        plv2.addWidget(btn_revert)
        btn_del_p = QPushButton('删除照片框'); btn_del_p.setProperty('role','danger')
        btn_del_p.clicked.connect(lambda: self._emit('delete', True))
        plv2.addWidget(btn_del_p)
        layout.addWidget(self.photo_widget)
        self.photo_widget.setVisible(False)

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        # ===== 5. 导出 PDF（底部固定，始终可见）=====
        footer = QWidget()
        footer.setObjectName('sideFooter')
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(14, 10, 14, 14)
        btn_pdf = QPushButton('导出 PDF')
        btn_pdf.setProperty('role', 'primary')
        btn_pdf.clicked.connect(self.export_pdf.emit)
        fl.addWidget(btn_pdf)
        outer.addWidget(footer, 0)

        # 装填字体下拉（首次）
        self._refresh_font_combo()

    def _emit(self, prop, val):
        if self._building: return
        self.text_changed.emit(prop, val)

    def _on_direction_clicked(self, direction):
        # 竖排时左/中/右对齐无意义 → 置灰
        self._set_align_enabled(direction == 'horizontal')
        self._emit('direction', direction)

    def _set_align_enabled(self, enabled):
        for b in (self.btn_align_l, self.btn_align_c, self.btn_align_r):
            b.setEnabled(enabled)

    # ===== 模板列表 =====
    def _refresh_template_list(self):
        self.tpl_list.clear()
        for name, mtime, path in self.template_store.list():
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, path)
            self.tpl_list.addItem(it)

    def _on_save_tpl(self):
        name = self.tpl_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, '提示', '请填模板名')
            return
        self.save_template.emit(name)
        self._refresh_template_list()

    def _on_load_tpl(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.load_template.emit(path)

    def _on_load_tpl_clicked(self):
        it = self.tpl_list.currentItem()
        if it: self._on_load_tpl(it)

    def _on_delete_tpl(self):
        it = self.tpl_list.currentItem()
        if not it: return
        if QMessageBox.question(self, '确认', f'删除模板"{it.text()}"？') != QMessageBox.StandardButton.Yes:
            return
        self.delete_template.emit(it.data(Qt.ItemDataRole.UserRole))
        self._refresh_template_list()

    # ===== 导入字体列表 =====
    def _refresh_imported_fonts_list(self):
        self.imp_font_list.clear()
        for fam in self.font_manager.imported_families():
            it = QListWidgetItem(f'★ {fam}'); it.setData(Qt.ItemDataRole.UserRole, fam)
            self.imp_font_list.addItem(it)
        self._refresh_font_combo()

    def _on_remove_font(self, item):
        fam = item.data(Qt.ItemDataRole.UserRole)
        self.remove_font.emit(fam)
        self._refresh_imported_fonts_list()

    # ===== 字体下拉 =====
    def _refresh_font_combo(self):
        self._building = True
        cur = self.font_combo.currentText()
        self.font_combo.clear()
        # 导入字体放最前（带 ★ 前缀仅显示，value 是 family）
        imp = self.font_manager.imported_families()
        for fam in imp:
            self.font_combo.addItem(f'★ {fam}', fam)
        # 系统字体
        for fam in self.font_manager.system_families():
            if fam not in imp:
                self.font_combo.addItem(fam, fam)
        # 恢复选中
        idx = self.font_combo.findData(cur)
        if idx >= 0: self.font_combo.setCurrentIndex(idx)
        self._building = False

    # ===== 颜色选择 =====
    def _pick_color(self):
        cur = QColor(self.btn_color.text())
        c = QColorDialog.getColor(cur, self, '选择字色')
        if c.isValid():
            hex_ = c.name()
            self.btn_color.setText(hex_)
            self.btn_color.setStyleSheet(f'background:{hex_}; color:{"#fff" if c.lightness()<128 else "#000"};')
            self._emit('color', hex_)

    # ===== 同步选中的框 → 面板 UI =====
    def bind_selection(self, item):
        self._current_item = item
        self._building = True
        is_text = isinstance(item, TextBoxItem)
        is_photo = isinstance(item, PhotoBoxItem)
        # 照片框 → 显示照片面板；文字框 / 无选中 → 显示文字面板
        self.props_widget.setVisible(not is_photo)
        self.photo_widget.setVisible(is_photo)
        self.props_widget.setEnabled(is_text)
        self.style_title.setText('照片框' if is_photo else '文字框样式')
        if not is_text:
            self._building = False
            return
        f = item.font()
        idx = self.font_combo.findData(f.family())
        if idx >= 0: self.font_combo.setCurrentIndex(idx)
        self.size_spin.setValue(max(4, f.pointSize() if f.pointSize() > 0 else 18))
        self.btn_bold.setChecked(f.bold())
        self.btn_italic.setChecked(f.italic())
        opt = item.document().defaultTextOption()
        a = opt.alignment()
        self.btn_align_l.setChecked(bool(a & Qt.AlignmentFlag.AlignLeft))
        self.btn_align_c.setChecked(bool(a & Qt.AlignmentFlag.AlignHCenter))
        self.btn_align_r.setChecked(bool(a & Qt.AlignmentFlag.AlignRight))
        c = item.defaultTextColor()
        self.btn_color.setText(c.name())
        self.btn_color.setStyleSheet(f'background:{c.name()}; color:{"#fff" if c.lightness()<128 else "#000"};')
        d = getattr(item, '_direction', 'horizontal')
        self.btn_dir_h.setChecked(d == 'horizontal')
        self.btn_dir_v.setChecked(d == 'vertical')
        self._set_align_enabled(d == 'horizontal')
        self._building = False
