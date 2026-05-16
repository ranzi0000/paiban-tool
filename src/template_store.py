"""模板保存/加载（JSON 文件，存到 app data 目录）"""
import os
import json
import base64
import time
from pathlib import Path
from typing import Optional
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice

from font_manager import app_data_dir


def templates_dir() -> Path:
    d = app_data_dir() / 'templates'
    d.mkdir(parents=True, exist_ok=True)
    return d


def pixmap_to_base64(pixmap: QPixmap) -> str:
    arr = QByteArray()
    buf = QBuffer(arr)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, 'PNG')
    return base64.b64encode(bytes(arr)).decode('ascii')


def pixmap_from_base64(b64: str) -> QPixmap:
    raw = base64.b64decode(b64)
    p = QPixmap()
    p.loadFromData(raw, 'PNG')
    return p


class TemplateStore:
    def list(self):
        """[(name, mtime, file_path)] 按修改时间倒序"""
        out = []
        for f in templates_dir().glob('*.json'):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    d = json.load(fp)
                out.append((d.get('name', f.stem), os.path.getmtime(f), f))
            except Exception:
                continue
        out.sort(key=lambda t: -t[1])
        return out

    def save(self, name: str, data: dict):
        """data 必须含 orient, bg_image_base64, boxes"""
        safe_name = ''.join(c for c in name if c not in '\\/:*?"<>|').strip() or 'untitled'
        data['name'] = name
        data['saved_at'] = time.time()
        f = templates_dir() / f'{safe_name}.json'
        with open(f, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        return f

    def load(self, path: Path) -> dict:
        with open(path, 'r', encoding='utf-8') as fp:
            return json.load(fp)

    def delete(self, path: Path):
        try:
            os.remove(path)
        except Exception:
            pass

    def export_all(self, dest_file: str):
        """导出所有模板到一个 JSON 文件"""
        items = []
        for name, _, path in self.list():
            items.append(self.load(path))
        with open(dest_file, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def import_bundle(self, src_file: str) -> int:
        with open(src_file, 'r', encoding='utf-8') as f:
            arr = json.load(f)
        if not isinstance(arr, list):
            raise ValueError('文件格式应为模板数组')
        count = 0
        for d in arr:
            name = d.get('name', 'imported')
            self.save(name, d)
            count += 1
        return count
