"""字体管理：系统字体 + 用户导入字体"""
import os
import json
from pathlib import Path
from PyQt6.QtGui import QFontDatabase


def app_data_dir() -> Path:
    """跨平台应用数据目录"""
    if os.name == 'nt':   # Windows
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:                  # macOS / Linux
        base = Path.home() / '.paiban-tool'
    d = base / 'paiban-tool'
    d.mkdir(parents=True, exist_ok=True)
    return d


def imported_fonts_dir() -> Path:
    d = app_data_dir() / 'fonts'
    d.mkdir(parents=True, exist_ok=True)
    return d


class FontManager:
    """管理"系统已装字体" + "用户导入字体"。Qt 字体引擎宽容，几乎所有 .ttf/.otf 都能加载。"""

    def __init__(self):
        self._imported = []   # [{'name': family, 'file': path}]
        self._font_db = QFontDatabase
        # 启动时把之前导入的字体重新加载（持久化在 app_data/fonts/ 目录）
        self._load_persisted_fonts()

    def system_families(self):
        """系统已装字体家族列表"""
        return self._font_db.families()

    def imported_families(self):
        return [f['name'] for f in self._imported]

    def all_families(self):
        """系统 + 导入。导入的在最前，加 ★ 前缀以便用户识别（在 UI 层加）"""
        sys_fams = set(self.system_families())
        imp = [f['name'] for f in self._imported if f['name'] in sys_fams]
        # 已加载的导入字体确实在系统列表里（addApplicationFont 后），这里去重
        return self.system_families()

    def import_font(self, path: str):
        """加载本地字体文件并持久化复制到 app data 目录。返回 (ok, family_name 或 错误描述)"""
        if not os.path.exists(path):
            return False, f'文件不存在: {path}'
        # 复制到 app data 目录（持久化）
        import shutil
        dest = imported_fonts_dir() / os.path.basename(path)
        if str(dest) != path:
            try:
                shutil.copy2(path, dest)
            except Exception as e:
                return False, f'复制字体失败: {e}'
        # 加载到 QFontDatabase
        font_id = self._font_db.addApplicationFont(str(dest))
        if font_id == -1:
            return False, f'Qt 加载字体失败（文件可能损坏或格式不支持）'
        families = self._font_db.applicationFontFamilies(font_id)
        if not families:
            return False, f'字体已加载但取不到家族名'
        family = families[0]
        self._imported.append({'name': family, 'file': str(dest)})
        self._save_index()
        return True, family

    def remove_imported(self, family: str):
        """删除导入字体"""
        for f in self._imported[:]:
            if f['name'] == family:
                try:
                    os.remove(f['file'])
                except Exception:
                    pass
                self._imported.remove(f)
        self._save_index()

    def _index_file(self) -> Path:
        return imported_fonts_dir() / '_index.json'

    def _save_index(self):
        with open(self._index_file(), 'w', encoding='utf-8') as f:
            json.dump(self._imported, f, ensure_ascii=False, indent=2)

    def _load_persisted_fonts(self):
        idx = self._index_file()
        if not idx.exists():
            return
        try:
            with open(idx, 'r', encoding='utf-8') as f:
                self._imported = json.load(f)
        except Exception:
            self._imported = []
        for f in self._imported[:]:
            if os.path.exists(f['file']):
                self._font_db.addApplicationFont(f['file'])
            else:
                self._imported.remove(f)
