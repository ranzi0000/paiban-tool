"""验证 v0.5.0 修复 + UX 改进
跑：QT_QPA_PLATFORM=offscreen python3 tests/test_charformat_and_ux.py
"""
import os, sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QColor, QTextCursor, QKeyEvent
from PyQt6.QtCore import Qt, QEvent, QPointF

from canvas import TextBoxItem, PhotoBoxItem, CanvasScene, CanvasView

app = QApplication.instance() or QApplication(sys.argv)
results = []

def check(name, cond, msg=''):
    mark = '✓' if cond else '✗'
    results.append((cond, name))
    print(f"  {mark} {name}{(' — ' + msg) if msg else ''}")


# ============== 测试 1: 编辑模式后改字号能生效（核心 bug）==============
print('\n[1] 编辑模式后改字号 → charFormat 同步')
scene = CanvasScene()
item = TextBoxItem(scene)
scene.addItem(item)

# 模拟双击进入编辑 + 键盘输入（用 cursor.insertText 模拟）
item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
item.setPlainText('')
cur = item.textCursor()
cur.insertText('王老五')

# 输入完，cursor 的 charFormat 已被 Qt 锁住为 18pt
fmt_before = QTextCursor(item.document())
fmt_before.select(QTextCursor.SelectionType.Document)
size_before = fmt_before.charFormat().font().pointSize()

# 模拟用户点 +/- 按钮：失焦 → 改字号
item.clearFocus()
item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
f = item.font()
f.setPointSize(48)
item.setFont(f)

# 验证 charFormat 也变了
fmt_after = QTextCursor(item.document())
fmt_after.select(QTextCursor.SelectionType.Document)
size_after = fmt_after.charFormat().font().pointSize()

check('编辑后字号生效（charFormat 同步）',
      size_after == 48,
      f'前={size_before}pt 后={size_after}pt')


# ============== 测试 2: 字色也能在编辑模式后生效 ==============
print('\n[2] 编辑模式后改字色 → charFormat 同步')
item2 = TextBoxItem(scene)
scene.addItem(item2)
item2.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
item2.setPlainText('')
item2.textCursor().insertText('测试')

item2.clearFocus()
item2.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
item2.setDefaultTextColor(QColor('#ff0000'))

c = QTextCursor(item2.document()); c.select(QTextCursor.SelectionType.Document)
color_after = c.charFormat().foreground().color().name()
check('字色生效', color_after == '#ff0000', f'实际={color_after}')


# ============== 测试 3: 加粗也能在编辑模式后生效 ==============
print('\n[3] 编辑模式后加粗 → charFormat 同步')
item3 = TextBoxItem(scene)
scene.addItem(item3)
item3.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
item3.setPlainText('')
item3.textCursor().insertText('粗体')
item3.clearFocus()
item3.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

f = item3.font(); f.setBold(True)
item3.setFont(f)
c = QTextCursor(item3.document()); c.select(QTextCursor.SelectionType.Document)
bold_after = c.charFormat().font().bold()
check('加粗生效', bold_after, f'bold={bold_after}')


# ============== 测试 4: 模板往返还原后再改字号也生效 ==============
print('\n[4] from_dict 还原后改字号 → charFormat 同步')
item_src = TextBoxItem(scene)
item_src.setPlainText('王老五')
f = item_src.font(); f.setPointSize(24); item_src.setFont(f)
d = item_src.to_dict()

item_restored = TextBoxItem.from_dict(d, scene)
scene.addItem(item_restored)
# 还原后改字号
f2 = item_restored.font(); f2.setPointSize(64); item_restored.setFont(f2)
c = QTextCursor(item_restored.document()); c.select(QTextCursor.SelectionType.Document)
size = c.charFormat().font().pointSize()
check('from_dict 后字号同步', size == 64, f'实际={size}pt')


# ============== 测试 5: 竖排不受影响 ==============
print('\n[5] 竖排改字号 boundingRect 同步变大')
item_v = TextBoxItem(scene)
scene.addItem(item_v)
item_v.setPlainText('竖排')
item_v.set_direction('vertical')
br_before = item_v.boundingRect()
f = item_v.font(); f.setPointSize(60); item_v.setFont(f)
br_after = item_v.boundingRect()
check('竖排字号变大 → boundingRect 变大',
      br_after.height() > br_before.height() * 1.5,
      f'前 h={br_before.height():.0f} 后 h={br_after.height():.0f}')


# ============== 测试 6: CanvasView 快捷键 - Delete 删框 ==============
print('\n[6] Delete 键删除选中框')
view = CanvasView()
view.show()
v_scene = view.scene_
v_item = TextBoxItem(v_scene)
v_scene.addItem(v_item)
v_item.setSelected(True)

# 模拟 Delete 键
ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete,
               Qt.KeyboardModifier.NoModifier)
view.keyPressEvent(ev)
check('Delete 删除选中框',
      v_item not in v_scene.items(),
      f'item still in scene? {v_item in v_scene.items()}')


# ============== 测试 7: 方向键微移 ==============
print('\n[7] 方向键微移文字框')
v_item2 = TextBoxItem(v_scene)
v_scene.addItem(v_item2)
v_item2.setPos(100, 100)
v_item2.setSelected(True)

ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
view.keyPressEvent(ev)
check('右键 1px 移动', v_item2.pos().x() == 101, f'x={v_item2.pos().x()}')

ev_shift = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
view.keyPressEvent(ev_shift)
check('Shift+下 10px 移动', v_item2.pos().y() == 110, f'y={v_item2.pos().y()}')


# ============== 测试 8: Ctrl+D 复制 ==============
print('\n[8] Ctrl+D 复制选中框')
# 清掉前面测试残留的选中状态，保证隔离
for i in list(v_scene.items()):
    if hasattr(i, 'setSelected'):
        i.setSelected(False)
v_item3 = TextBoxItem(v_scene)
v_scene.addItem(v_item3)
v_item3.setPos(200, 200)
v_item3.setPlainText('原件')
v_item3.setSelected(True)
n_before = len([i for i in v_scene.items() if isinstance(i, TextBoxItem)])

ev_d = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
view.keyPressEvent(ev_d)
n_after = len([i for i in v_scene.items() if isinstance(i, TextBoxItem)])
check('Ctrl+D 复制出新副本', n_after == n_before + 1, f'前={n_before} 后={n_after}')

# 检查副本位置 +12/+12 且选中状态转移
copies = [i for i in v_scene.items()
          if isinstance(i, TextBoxItem) and i is not v_item3 and i.isSelected()]
if copies:
    check('副本位置偏移 +12/+12',
          copies[0].pos().x() == 212 and copies[0].pos().y() == 212,
          f'pos=({copies[0].pos().x()},{copies[0].pos().y()})')
    check('副本选中、原件取消选中',
          not v_item3.isSelected() and copies[0].isSelected())
else:
    check('副本能找到', False)


# ============== 测试 9: 编辑模式下按 Delete 不会删框（让 Qt 处理）==============
print('\n[9] 编辑模式下 Delete 走文字编辑，不删框')
v_item4 = TextBoxItem(v_scene)
v_scene.addItem(v_item4)
v_item4.setSelected(True)
v_item4.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
view.keyPressEvent(ev)
check('编辑模式下 Delete 不删框',
      v_item4 in v_scene.items())


# ============== 测试 10: 字号 spinbox 步长 = 1 ==============
print('\n[10] side_panel 字号步长 = 1')
from font_manager import FontManager
from template_store import TemplateStore
from side_panel import SidePanel
fm = FontManager(); ts = TemplateStore()
panel = SidePanel(fm, ts)
check('size_spin singleStep == 1', panel.size_spin.singleStep() == 1,
      f'实际={panel.size_spin.singleStep()}')


# ============== 汇总 ==============
print('\n' + '='*50)
total = len(results)
passed = sum(1 for ok, _ in results if ok)
print(f'结果：{passed}/{total} 通过')
if passed < total:
    print('失败项：')
    for ok, name in results:
        if not ok:
            print(f'  ✗ {name}')
    sys.exit(1)
print('全部通过 ✓')
