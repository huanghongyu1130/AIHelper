import sys
import os
import threading
import asyncio
import speech_recognition as sr
import ctypes # 使用 ctypes 呼叫 Win32 API 進行按鍵輪詢
import time
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from agent import get_agent_async, Runner, InMemorySessionService, InMemoryArtifactService, RunConfig, StreamingMode, types
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QConicalGradient, QBrush, QLinearGradient, QPixmap, QImage
from agent import get_screenshot_part

class ScreenGlowOverlay(QWidget):
    """全螢幕邊框發光特效視窗 (霓虹波浪 + 漸層淡入淡出版)"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(QApplication.primaryScreen().geometry())

        # 動畫與特效參數
        self.angle = 0
        self.opacity = 0.0
        self.target_opacity = 0.0
        self.border_width = 50 # 加寬邊框以顯示漸層效果
        self.mask_pixmap = None
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)

    def resizeEvent(self, event):
        # 當螢幕大小改變時，重新產生遮罩
        self.generate_mask()
        super().resizeEvent(event)

    def generate_mask(self):
        """產生邊緣實心、內部透明的遮罩"""
        if self.width() <= 0 or self.height() <= 0: return
        
        img = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        bw = self.border_width
        w, h = self.width(), self.height()
        
        # 定義漸層: 0.0(邊緣)=不透明, 1.0(內部)=透明
        # 上邊框
        g_top = QLinearGradient(0, 0, 0, bw)
        g_top.setColorAt(0, QColor(255, 255, 255, 255))
        g_top.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(0, 0, w, bw, g_top)
        
        # 下邊框
        g_bottom = QLinearGradient(0, h, 0, h - bw)
        g_bottom.setColorAt(0, QColor(255, 255, 255, 255))
        g_bottom.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(0, h - bw, w, bw, g_bottom)
        
        # 左邊框
        g_left = QLinearGradient(0, 0, bw, 0)
        g_left.setColorAt(0, QColor(255, 255, 255, 255))
        g_left.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(0, 0, bw, h, g_left)
        
        # 右邊框
        g_right = QLinearGradient(w, 0, w - bw, 0)
        g_right.setColorAt(0, QColor(255, 255, 255, 255))
        g_right.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(w - bw, 0, bw, h, g_right)
        
        p.end()
        self.mask_pixmap = QPixmap.fromImage(img)

    def fade_in(self):
        self.target_opacity = 1.0
        if not self.timer.isActive():
            self.show()
            self.timer.start(30)

    def fade_out(self):
        self.target_opacity = 0.0

    def update_animation(self):
        # 1. 更新旋轉角度
        self.angle = (self.angle - 5) % 360

        # 2. 更新透明度 (淡入淡出)
        diff = self.target_opacity - self.opacity
        if abs(diff) < 0.05:
            self.opacity = self.target_opacity
            if self.opacity == 0.0:
                self.hide()
                self.timer.stop()
        else:
            self.opacity += diff * 0.2 # 平滑過渡
            
        self.update()

    def paintEvent(self, event):
        if self.opacity <= 0 or not self.mask_pixmap: return

        # 建立一個暫存的 Pixmap 來合成特效
        temp_pixmap = QPixmap(self.size())
        temp_pixmap.fill(Qt.GlobalColor.transparent)
        
        p = QPainter(temp_pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 步驟 A: 先畫出遮罩 (決定哪裡要顯示)
        p.drawPixmap(0, 0, self.mask_pixmap)
        
        # 步驟 B: 使用 SourceIn 模式填入霓虹色彩
        # (保留遮罩的不透明度，但將顏色替換為漸層)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        
        center = self.rect().center()
        gradient = QConicalGradient(center.x(), center.y(), self.angle)
        gradient.setColorAt(0.00, QColor(0, 255, 255))   # Cyan
        gradient.setColorAt(0.25, QColor(0, 0, 255))     # Blue
        gradient.setColorAt(0.50, QColor(128, 0, 128))   # Purple
        gradient.setColorAt(0.75, QColor(255, 0, 255))   # Magenta
        gradient.setColorAt(1.00, QColor(0, 255, 255))   # Cyan
        
        p.setBrush(QBrush(gradient))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(self.rect())
        p.end()
        
        # 步驟 C: 將合成好的 Pixmap 畫到螢幕上，並套用全域透明度
        painter = QPainter(self)
        painter.setOpacity(self.opacity)
        painter.drawPixmap(0, 0, temp_pixmap)

class VoiceAssistantWidget(QWidget):
    # 定義一個信號，用來在非 GUI 執行緒通知 GUI 更新
    status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.initUI()
        
        # 初始化全螢幕特效
        self.overlay = ScreenGlowOverlay()
        
        # 初始化 AI Agent 相關組件
        self.agent = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_async_loop, daemon=True).start()
        
        self.listening = False
        self.vad_mode = False  # VAD 模式狀態
        self.vad_thread_running = False # 避免重複啟動 VAD 執行緒
        
        # 連接信號
        self.status_signal.connect(self.update_status)

        # 啟動背景熱鍵監聽
        self.start_hotkey_listener()

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def initUI(self):
        # 1. 設定視窗屬性：無邊框、永遠在最上層
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        
        # 2. 設定背景透明
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 3. 調整視窗大小 (稍微加大以容納發光特效)
        # 改用 setMinimumSize 避免在高 DPI 下被內容撐開導致幾何設定錯誤
        self.setMinimumWidth(240)
        self.setMaximumWidth(600) # 限制最大寬度，強制長文字換行

        # 4. 主要佈局 (包含邊距，讓陰影不會被切掉)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        # 讓視窗大小根據內容自動調整 (最小與最大尺寸限制內)
        main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        # 5. 內容容器 (原本的介面樣式移到這裡)
        self.container = QWidget()
        self.container.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            border-radius: 15px;
            border: 2px solid #00ff00;
        """)
        
        # 容器內的佈局
        container_layout = QVBoxLayout()
        self.label = QLabel("等待呼叫...")
        self.label.setFont(QFont('Microsoft JhengHei', 12))
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: white; background: transparent; border: none;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        container_layout.addWidget(self.label)
        self.container.setLayout(container_layout)
        
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)

        # 將視窗移動到螢幕左上角
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.move(20, 20)

    def update_status(self, text):
        """更新 UI 顯示文字"""
        self.label.setText(text)
        # 強制調整視窗大小以適應新文字
        self.adjustSize()
        
        # 判斷是否為「活躍狀態」 (錄音中 或 VAD待命中 或 轉譯中)
        is_active = "聆聽中" in text or "VAD 待命中" in text or "轉譯中" in text
        
        if is_active:
            # 活躍模式：紅色背景 + 白色發光
            self.container.setStyleSheet("""
                background-color: rgba(255, 0, 0, 180);
                border-radius: 15px;
                border: 2px solid #ffffff;
            """)
            
            # 加入白色發光特效 (小視窗)
            glow = QGraphicsDropShadowEffect()
            glow.setBlurRadius(20)
            glow.setColor(QColor(255, 255, 255))
            glow.setOffset(0, 0)
            self.container.setGraphicsEffect(glow)
            
            # 顯示全螢幕邊框特效 (淡入)
            self.overlay.fade_in()
            
        else:
            # 待機模式：黑色背景 + 綠色邊框
            self.container.setStyleSheet("""
                background-color: rgba(0, 0, 0, 180);
                border-radius: 15px;
                border: 2px solid #00ff00;
            """)
            self.container.setGraphicsEffect(None) # 移除特效
            
            # 隱藏全螢幕邊框特效 (淡出)
            self.overlay.fade_out()

        self.show()

    async def process_with_ai(self, text):
        """將辨識出的文字送交 AI 處理"""
        try:
            if self.agent is None:
                self.status_signal.emit("🤖 正在初始化 AI...")
                self.agent = await get_agent_async("voice_session")
            
            self.status_signal.emit("🤖 AI 思考中...")
            
            session_service = InMemorySessionService()
            artifacts_service = InMemoryArtifactService()
            session = await session_service.create_session(state={}, app_name='voice_app', user_id="user")
            
            runner = Runner(
                app_name='voice_app',
                agent=self.agent,
                artifact_service=artifacts_service,
                session_service=session_service,
            )
            
            parts = [types.Part(text=text)]
            
            # 在語音對話時也自動加入截圖
            screenshot_part = get_screenshot_part()
            if screenshot_part:
                parts.append(screenshot_part)
            
            content = types.Content(role='user', parts=parts)
            full_response = ""
            
            async for event in runner.run_async(
                session_id=session.id,
                user_id=session.user_id,
                new_message=content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=10)
            ):
                if event.content and event.partial:
                    text_part = event.content.parts[0].text
                    if text_part:
                        full_response += text_part
                        # 實時更新顯示內容
                        self.status_signal.emit(f"🤖 AI：{full_response}")
                elif not event.partial and event.content:
                    # 最終回應完成
                    pass

        except Exception as e:
            self.status_signal.emit(f"⚠️ AI 錯誤: {e}")

    def start_voice_recognition(self):
        """真正的語音識別邏輯"""
        if self.vad_mode:
            self.status_signal.emit("⚠️ VAD 模式開啟中")
            return

        if self.listening: return
        self.listening = True
        
        def recognition_thread():
            self.status_signal.emit("🔴 聆聽中...請說話")
            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=5, phrase_time_limit=10)
                    self.status_signal.emit("🔄 轉譯中...")
                    text = r.recognize_google(audio, language="zh-TW")
                    self.status_signal.emit(f"你說：{text}")
                    
                    # 異步呼叫 AI 處理
                    asyncio.run_coroutine_threadsafe(self.process_with_ai(text), self.loop)

            except sr.UnknownValueError:
                self.status_signal.emit("❌ 無法辨識 (聽不清楚)")
                threading.Timer(3.0, lambda: self.status_signal.emit("等待呼叫...")).start()
            except sr.RequestError:
                self.status_signal.emit("⚠️ 網路錯誤")
                threading.Timer(3.0, lambda: self.status_signal.emit("等待呼叫...")).start()
            except Exception as e:
                self.status_signal.emit(f"⚠️ 錯誤: {e}")
                threading.Timer(3.0, lambda: self.status_signal.emit("等待呼叫...")).start()
            finally:
                self.listening = False

        threading.Thread(target=recognition_thread, daemon=True).start()

    def toggle_vad_mode(self):
        """切換 VAD 模式"""
        self.vad_mode = not self.vad_mode
        if self.vad_mode:
            self.status_signal.emit("🎙️ VAD 模式已啟動")
            if not self.vad_thread_running:
                threading.Thread(target=self.run_vad_loop, daemon=True).start()
        else:
            self.status_signal.emit("🛑 VAD 模式已關閉")

    def run_vad_loop(self):
        """VAD 循環監聽"""
        if self.vad_thread_running: return
        self.vad_thread_running = True
        
        r = sr.Recognizer()
        
        try:
            with sr.Microphone() as source:
                self.status_signal.emit("調整環境噪音中...")
                r.adjust_for_ambient_noise(source, duration=1)
                
                while self.vad_mode:
                    if self.listening:
                        threading.Event().wait(0.5)
                        continue

                    try:
                        self.status_signal.emit("👂 VAD 待命中...")
                        # timeout=1: 每秒檢查一次是否有人說話
                        audio = r.listen(source, timeout=1, phrase_time_limit=10)
                        
                        self.listening = True
                        self.status_signal.emit("🔄 轉譯中...")
                        
                        try:
                            text = r.recognize_google(audio, language="zh-TW")
                            self.status_signal.emit(f"你說：{text}")
                            # VAD 模式也串接 AI
                            asyncio.run_coroutine_threadsafe(self.process_with_ai(text), self.loop)
                        except sr.UnknownValueError:
                            pass
                        except sr.RequestError:
                            self.status_signal.emit("⚠️ 網路錯誤")
                        except Exception as e:
                            print(f"VAD Error: {e}")
                            
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        self.status_signal.emit(f"⚠️ 錯誤: {e}")
                        threading.Event().wait(1)
                    finally:
                        self.listening = False
                        
        except Exception as e:
            self.status_signal.emit(f"⚠️ 麥克風錯誤: {e}")
            self.vad_mode = False
        finally:
            self.vad_thread_running = False

    def start_hotkey_listener(self):
        """在背景執行緒使用 GetAsyncKeyState 輪詢監聽鍵盤"""
        def check_key():
            # 定義虛擬鍵碼 (Virtual-Key Codes)
            VK_OEM_2 = 0xBF # '/?' 鍵
            VK_DIVIDE = 0x6F # 數字鍵盤 '/' 鍵
            VK_F12 = 0x7B
            VK_ESCAPE = 0x1B
            
            while True:
                try:
                    # 檢查 '/' 鍵 (主鍵盤或數字鍵盤)
                    if (ctypes.windll.user32.GetAsyncKeyState(VK_OEM_2) & 0x8000) or \
                       (ctypes.windll.user32.GetAsyncKeyState(VK_DIVIDE) & 0x8000):
                        # 呼叫語音辨識
                        # 使用 QTimer.singleShot 在主執行緒觸發，避免執行緒安全問題
                        # 但這裡原本邏輯是直接呼叫，且 start_voice_recognition 內部有鎖，暫時保持直接呼叫
                        if not self.listening and not self.vad_mode:
                            self.start_voice_recognition()
                            time.sleep(0.5) # 簡單防抖動
                    
                    # 檢查 F12
                    elif ctypes.windll.user32.GetAsyncKeyState(VK_F12) & 0x8000:
                        self.toggle_vad_mode()
                        time.sleep(0.5) # 簡單防抖動
                        
                    # 檢查 ESC (退出)
                    elif ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                        QApplication.instance().quit()
                        break
                        
                    time.sleep(0.05) # 20Hz 採樣率，降低 CPU 使用率
                except Exception as e:
                    print(f"Hotkey Error: {e}")
                    time.sleep(1)

        t = threading.Thread(target=check_key, daemon=True)
        t.start()

if __name__ == '__main__':
    # 解決 DPI 縮放問題
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # 設定 DPI 縮放策略
    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    ex = VoiceAssistantWidget()
    ex.show()
    sys.exit(app.exec())