import sys
import os
import time
import requests
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSize
from PyQt5.QtGui import QPixmap, QMovie, QCursor
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QMenu, QMessageBox, QDesktopWidget)

class DeskPet(QWidget):
    def __init__(self):
        super().__init__()
        
        # --- 路径与配置 ---
        self.base_dir = r"C:\Users\YJP\Desktop\deskpet"
        self.image_path = os.path.join(self.base_dir, "fgyy1.png")
        self.readme_path = os.path.join(self.base_dir, "readme.md")
        
        # api输入口
        self.api_key = "sk-687424e1eaa04be49d7f33e3c6911aca"
        self.api_url = "https://api.deepseek.com/v1/chat/completions" 
        
        # --- 初始化状态 ---
        self.is_follow_mouse = False
        self.mouse_drag_pos = QPoint()
        self.scale_factor = 1.0
        self.original_size = QSize(200, 200) # 默认图片尺寸
        
        # 对话框状态控制
        self.full_text = ""
        self.current_text = ""
        self.text_index = 0
        self.is_typing = False
        self.text_complete_time = 0
        
        # 日程提醒（示例：12:00 吃饭）
        self.reminders = [
            {"time": "12:00", "task": "喂，该吃饭了。"},
            {"time": "18:00", "task": "主公大人的任务…不对，是你该吃晚饭了。"}
        ]
        
        self.init_ui()
        self.init_timers()

    def init_ui(self):
        # 设置窗口属性：无边框、不在任务栏显示、窗口置顶、透明背景
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 布局
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        
        # 1. 对话气泡标签
        self.talk_label = QLabel("", self)
        self.talk_label.setAlignment(Qt.AlignCenter)
        self.talk_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 85%);
                border: 2px solid #2c3e50;
                border-radius: 10px;
                padding: 8px;
                font-family: 'Microsoft YaHei';
                font-size: 12px;
                color: #333333;
            }
        """)
        self.talk_label.hide() # 默认隐藏
        self.layout.addWidget(self.talk_label)
        
        # 2. 角色图片标签
        self.pet_label = QLabel(self)
        if os.path.exists(self.image_path):
            self.pixmap = QPixmap(self.image_path)
        else:
            # 找不到图片时的兜底图
            self.pixmap = QPixmap(200, 200)
            self.pixmap.fill(Qt.blue) 
        self.update_scale()
        self.layout.addWidget(self.pet_label)
        
        # 3. 输入框
        self.input_box = QLineEdit(self)
        self.input_box.setPlaceholderText("跟义勇说话... (回车发送)")
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 4px;
                background: rgba(255, 255, 255, 70%);
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #34495e;
                background: rgba(255, 255, 255, 95%);
            }
        """)
        self.input_box.returnPressed.connect(self.send_to_deepseek)
        self.layout.addWidget(self.input_box)
        
        self.setLayout(self.layout)
        
        # 初始位置：屏幕右下角
        screen = QDesktopWidget().screenGeometry()
        self.move(screen.width() - self.width() - 50, screen.height() - self.height() - 100)
        self.show()

    def init_timers(self):
        # 打字机定时器
        self.type_timer = QTimer()
        self.type_timer.timeout.connect(self.type_effect)
        
        # 气泡淡出/消失定时器
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.handle_fadeout)
        
        # 物理重力与边缘检测定时器 (约60帧/秒)
        self.physics_timer = QTimer()
        self.physics_timer.timeout.connect(self.apply_physics)
        self.physics_timer.start(16)
        
        # 日程轮询定时器 (每10秒检查一次)
        self.reminder_timer = QTimer()
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(10000)

    # --- 基础物理与交互 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_follow_mouse = True
            self.mouse_drag_pos = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            
    def mouseMoveEvent(self, event):
        if Qt.LeftButton and self.is_follow_mouse:
            self.move(event.globalPos() - self.mouse_drag_pos)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_follow_mouse = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()

    def apply_physics(self):
        # 如果正在拖拽，不应用物理引擎
        if self.is_follow_mouse:
            return
            
        screen = QDesktopWidget().screenGeometry()
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        
        # 检测是否靠在左右边缘 (阈值设为10像素)
        margin = 10
        if x <= margin:
            # 吸附左边缘
            self.move(0, y)
            return
        elif x + w >= screen.width() - margin:
            # 吸附右边缘
            self.move(screen.width() - w, y)
            return
            
        # 如果在屏幕中间，模拟重力下落到底部任务栏上方
        # 假设任务栏高度为40像素
        target_y = screen.height() - h - 40
        if y < target_y:
            speed = int((target_y - y) * 0.2) + 1 # 弹性缓动下落
            self.move(x, min(y + speed, target_y))

    # --- 基础大小变化 ---
    def wheelEvent(self, event):
        # 滚轮向上放大，向下缩小
        angle = event.angleDelta().y()
        if angle > 0:
            self.scale_factor = min(self.scale_factor + 0.1, 2.0) # 最大2倍
        else:
            self.scale_factor = max(self.scale_factor - 0.1, 0.5) # 最小0.5倍
            
        self.update_scale()
        event.accept()

    def update_scale(self):
        new_w = int(self.original_size.width() * self.scale_factor)
        new_h = int(self.original_size.height() * self.scale_factor)
        
        # 缩放图片并应用
        scaled_pixmap = self.pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pet_label.setPixmap(scaled_pixmap)
        self.pet_label.setFixedSize(scaled_pixmap.size())
        self.setFixedSize(self.layout.sizeHint())

    # --- 右键菜单与说明书  ---
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        help_action = menu.addAction("帮助/说明")
        exit_action = menu.addAction("让义勇休息 (退出)")
        
        action = menu.exec_(self.mapToGlobal(event.pos()))
        
        if action == help_action:
            self.open_readme()
        elif action == exit_action:
            QApplication.quit()

    def open_readme(self):
        # 如果文件不存在，自动创建一个
        if not os.path.exists(self.readme_path):
            with open(self.readme_path, "w", encoding="utf-8") as f:
                f.write("# 富冈义勇 桌宠说明书\n\n- **鼠标左键**：拖拽移动\n- **鼠标滚轮**：缩放大小\n- **右键菜单**：查看帮助/退出\n- **下方输入框**：与义勇联网对话")
        
        # 调用系统默认文本编辑器打开
        os.startfile(self.readme_path)

    # --- 日程提醒助手  ---
    def check_reminders(self):
        current_time = time.strftime("%H:%M")
        for item in self.reminders:
            if item["time"] == current_time:
                self.activate_reminder(item["task"])

    def activate_reminder(self, task_content):
        # 窗口置顶并唤醒
        self.activateWindow()
        self.raise_()
        
        # 播放系统提示音
        if sys.platform == "win32":
            import winsound
            winsound.MessageBeep()
            
        # 弹出对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowFlags(Qt.WindowStaysOnTopHint)
        msg_box.setWindowTitle("重要日程提醒")
        msg_box.setText(f"义勇提醒你：\n\n【{task_content}】")
        msg_box.addButton("知道了", QMessageBox.AcceptRole)
        msg_box.exec_()

    # --- 对话逻辑与打字机动画 ---
    def start_speaking(self, text):
        self.full_text = text
        self.current_text = ""
        self.text_index = 0
        self.is_typing = True
        self.talk_label.setText("")
        self.talk_label.show()
        
        # 每50毫秒打印一个字
        self.type_timer.start(50)
        self.fade_timer.stop()

    def type_effect(self):
        if self.text_index < len(self.full_text):
            self.current_text += self.full_text[self.text_index]
            self.talk_label.setText(self.current_text)
            self.text_index += 1
            self.adjustSize()
        else:
            self.type_timer.stop()
            self.is_typing = False
            self.text_complete_time = time.time()
            # 完全显示后存留3秒（按要求：没有下一句停3秒淡出）
            self.fade_timer.start(3000)

    def handle_fadeout(self):
        self.talk_label.hide()
        self.fade_timer.stop()
        self.adjustSize()

    # 点击对话框快速显示或切歌
    def mousePressEvent_talk(self, event):
        # 劫持气泡的点击事件
        now = time.time()
        if self.is_typing:
            # 如果正在打字，直接显示完整对话
            self.type_timer.stop()
            self.talk_label.setText(self.full_text)
            self.is_typing = False
            self.text_complete_time = now
            self.fade_timer.start(3000)
        else:
            # 如果已显示完整，过0.5秒后再点击才会关闭/显示下一句
            if now - self.text_complete_time > 0.5:
                self.talk_label.hide()
                self.adjustSize()

    # 覆盖原生的事件，让气泡点击也能响应
    def eventFilter(self, obj, event):
        if obj == self.talk_label and event.type() == event.MouseButtonPress:
            self.mousePressEvent_talk(event)
            return True
        return super().eventFilter(obj, event)

    # --- DeepSeek 联网对话 ---
    def send_to_deepseek(self):
        user_text = self.input_box.text().strip()
        if not user_text:
            return
        
        self.input_box.clear()
        self.start_speaking("……（思考中）")
        
        # 异步/简易网络请求（注：为防界面卡死，此处用最快响应）
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 注入富冈义勇的角色设定
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是《鬼灭之刃》中的水柱富冈义勇。你性格高冷、沉默寡言、不擅长表达言辞，常被误解，但内心温柔正义。回答要简短、冷淡、带有义勇的口吻，字数控制在30字以内。常用口头禅：'我没有被讨厌。'"},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.7
        }
        
        try:
            # 这里的简单请求可能引发0.x秒微卡
            response = requests.post(self.api_url, json=data, headers=headers, timeout=5)
            if response.status_code == 200:
                reply = response.json()['choices'][0]['message']['content']
                self.start_speaking(reply)
            else:
                self.start_speaking("……（不想说话）。")
        except Exception:
            self.start_speaking("鎹鸦没带回消息……（网络错误）")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DeskPet()
    # 注册气泡的点击过滤
    app.installEventFilter(pet)
    sys.exit(app.exec_())
