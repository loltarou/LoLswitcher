import sys
import os
import json
import shutil
import subprocess
import time
import requests
import urllib3
import pyautogui
import win32gui
import win32con
import keyboard
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QSystemTrayIcon, QPushButton, QDialog, 
                             QLineEdit, QFrame, QListWidget)
from PyQt6.QtGui import QIcon, QPainter, QColor, QCursor, QPixmap
from PyQt6.QtCore import Qt, QByteArray, QThread, pyqtSignal, QSharedMemory
from PyQt6.QtSvg import QSvgRenderer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCAL_APP_DATA = os.environ.get('LOCALAPPDATA', '')
SWITCH_DIR = os.path.join(LOCAL_APP_DATA, 'Switch')
PROFILES_DIR = os.path.join(SWITCH_DIR, 'Profiles')
SETTINGS_FILE = os.path.join(SWITCH_DIR, 'settings.json')
RIOT_CLIENT_DIR = os.path.join(LOCAL_APP_DATA, 'Riot Games', 'Riot Client')
CREATE_NO_WINDOW = 0x08000000

FILES_TO_SWITCH = [
    {"filename": "RiotGamesPrivateSettings.yaml", "rel_path": "Data/RiotGamesPrivateSettings.yaml", "is_dir": False},
    {"filename": "Sessions", "rel_path": "Data/Sessions", "is_dir": True},
    {"filename": "RiotClientSettings.yaml", "rel_path": "Config/RiotClientSettings.yaml", "is_dir": False}
]

def get_api_key():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    env_paths = [
        os.path.join(base_dir, ".env"),
        os.path.join(SWITCH_DIR, ".env")
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("RIOT_API_KEY="):
                            key = line.split("=", 1)[1].strip()
                            key = key.strip("\"'")
                            return key
            except:
                pass
    return ""

class LolLauncherThread(QThread):
    def __init__(self, exe_path, riot_client_dir):
        super().__init__()
        self.exe_path = exe_path
        self.riot_client_dir = riot_client_dir

    def run(self):
        print("  -> [バックグラウンド] APIによるログイン完了を待機します...")
        logged_in = False
        for _ in range(30):
            time.sleep(1.0)
            lockfile_path = os.path.join(self.riot_client_dir, "Config", "lockfile")
            if not os.path.exists(lockfile_path):
                continue
            try:
                with open(lockfile_path, 'r', encoding='utf-8') as f:
                    data = f.read().split(':')
                if len(data) >= 5:
                    port = data[2]
                    password = data[3]
                    url = f"https://127.0.0.1:{port}/chat/v1/session"
                    response = requests.get(url, auth=('riot', password), verify=False, timeout=1)
                    if response.status_code == 200 and response.json().get('game_name'):
                        logged_in = True
                        break
            except:
                pass
                
        if not logged_in:
            print("[警告] ログインの完了を検知できませんでした。自動起動を中止します。")
            return
            
        print("  -> ログイン確認成功。クライアントを安定させるため5秒待機します...")
        time.sleep(5.0)
        
        print("  -> LoL起動コマンドを送信します...")
        try:
            subprocess.Popen([self.exe_path, "--launch-product=league_of_legends", "--launch-patchline=live"])
        except Exception as e:
            print(f"  -> [エラー] 起動コマンド送信失敗: {e}")
            return
            
        print("  -> [バックグラウンド] LeagueClient.exe の出現を監視します...")
        for i in range(15):
            time.sleep(2.0)
            try:
                output = subprocess.check_output(
                    ["tasklist", "/FI", "IMAGENAME eq LeagueClient.exe", "/NH"],
                    creationflags=CREATE_NO_WINDOW,
                    text=True
                )
                if "LeagueClient.exe" in output:
                    print("[成功] League of Legends の起動を確認しました！")
                    return
            except:
                pass
                
            if i == 5 or i == 10:
                print("  -> LoLが起動しないため、コマンドを再送信します...")
                try:
                    subprocess.Popen([self.exe_path, "--launch-product=league_of_legends", "--launch-patchline=live"])
                except:
                    pass
                    
        print("[警告] 指定時間内にLeague of Legendsの起動を確認できませんでした。")


class RankFetchThread(QThread):
    rank_fetched = pyqtSignal(str, str) 

    def __init__(self, accounts_to_fetch, api_key):
        super().__init__()
        self.accounts_to_fetch = accounts_to_fetch
        self.api_key = api_key

    def run(self):
        if not self.api_key:
            return
            
        headers = {"X-Riot-Token": self.api_key}
        tier_map = {
            "IRON": "I", "BRONZE": "B", "SILVER": "S", "GOLD": "G",
            "PLATINUM": "P", "EMERALD": "E", "DIAMOND": "D",
            "MASTER": "M", "GRANDMASTER": "GM", "CHALLENGER": "C"
        }
        div_map = {"I": "1", "II": "2", "III": "3", "IV": "4"}

        print(f"\n[診断] === ランク取得バックグラウンド処理 開始 ===")

        for acc in self.accounts_to_fetch:
            if "#" not in acc:
                continue
            name, tag = acc.split("#", 1)
            
            print(f"[診断] {acc} のランクを取得中...")
            url_account = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
            try:
                res1 = requests.get(url_account, headers=headers, timeout=5)
                if res1.status_code == 200:
                    puuid = res1.json().get("puuid")
                    
                    url_league = f"https://jp1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
                    res2 = requests.get(url_league, headers=headers, timeout=5)
                    tier_str = "un"
                    
                    if res2.status_code == 200:
                        data = res2.json()
                        for queue in data:
                            if queue.get("queueType") == "RANKED_SOLO_5x5":
                                t = queue.get("tier", "UNRANKED")
                                d = queue.get("rank", "")
                                if t.upper() == "UNRANKED":
                                    tier_str = "un"
                                else:
                                    t_initial = tier_map.get(t, t[:1] if t else "U")
                                    d_num = div_map.get(d, "")
                                    tier_str = f"{t_initial}{d_num}"
                                break
                                
                    print(f"[診断] {acc} のランク取得成功: {tier_str}")
                    self.rank_fetched.emit(acc, tier_str)
                else:
                    print(f"[エラー] {acc} のPUUID取得に失敗 (コード: {res1.status_code})")
            except Exception as e:
                print(f"[エラー] {acc} の通信中にエラー発生: {e}")
                
            time.sleep(0.5)
            
        print(f"[診断] === ランク取得バックグラウンド処理 終了 ===\n")


class AccountButton(QPushButton):
    rightClicked = pyqtSignal(str)
    leftClicked = pyqtSignal(str)

    def __init__(self, display_text, original_account_name, parent=None):
        super().__init__(display_text, parent)
        self.original_account_name = original_account_name

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit(self.original_account_name)
        elif event.button() == Qt.MouseButton.LeftButton:
            self.leftClicked.emit(self.original_account_name)
        super().mouseReleaseEvent(event)


class BaseSidePanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)
        self.auto_close = False

        self.button_style = """
            QPushButton { background-color: #3f4147; color: white; border: none; border-radius: 4px; padding: 8px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #4f545c; }
        """
        self.danger_button_style = """
            QPushButton { background-color: #da373c; color: white; border: none; border-radius: 4px; padding: 8px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #a1282c; }
        """
        self.primary_button_style = """
            QPushButton { background-color: #5865F2; color: white; border: none; border-radius: 4px; padding: 8px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #4752c4; }
        """
        self.input_style = """
            QLineEdit { background-color: #1e1f22; color: #dbdee1; border: 1px solid #1e1f22; border-radius: 4px; padding: 8px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #5865F2; }
        """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2b2d31"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange:
            if not self.isActiveWindow() and getattr(self, 'auto_close', False):
                self.reject()
        super().changeEvent(event)

    def move_beside(self, main_menu):
        self.adjustSize()
        geo = main_menu.geometry()
        screen = QApplication.primaryScreen().availableGeometry()
        x = geo.right() + 5
        y = geo.top()
        
        if x + self.width() > screen.right():
            x = geo.left() - self.width() - 5
            
        if y + self.height() > screen.bottom():
            y = screen.bottom() - self.height()
            
        self.move(x, y)

    def add_title(self, text):
        title = QLabel(text)
        title.setStyleSheet("color: #b5bac1; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: bold; padding: 4px 8px;")
        self.layout.addWidget(title)


class SideActionPanel(BaseSidePanel):
    def __init__(self, account_name, parent=None):
        super().__init__(parent)
        self.account_name = account_name
        self.action_result = None
        self.auto_close = True

        self.add_title(f"{account_name} の操作")

        btn_edit = QPushButton("変更")
        btn_edit.setStyleSheet(self.button_style)
        btn_edit.clicked.connect(self.on_edit)

        btn_delete = QPushButton("削除")
        btn_delete.setStyleSheet(self.danger_button_style)
        btn_delete.clicked.connect(self.on_delete)
        
        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet(self.button_style)
        btn_close.clicked.connect(self.reject)

        self.layout.addWidget(btn_edit)
        self.layout.addWidget(btn_delete)
        self.layout.addWidget(btn_close)
        
        self.adjustSize()

    def on_edit(self):
        self.action_result = 'edit'
        self.accept()

    def on_delete(self):
        self.action_result = 'delete'
        self.accept()


class SidePuuidPanel(BaseSidePanel):
    def __init__(self, account_name, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.auto_close = False
        self.add_title("PUUID ⇄ Riot ID")

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("Riot ID (Name#TAG)")
        self.input_id.setText(account_name)
        self.input_id.setStyleSheet(self.input_style)

        self.input_puuid = QLineEdit()
        self.input_puuid.setPlaceholderText("PUUID")
        self.input_puuid.setStyleSheet(self.input_style)

        btn_id_to_puuid = QPushButton("ID ➔ PUUID")
        btn_id_to_puuid.setStyleSheet(self.primary_button_style)
        btn_id_to_puuid.clicked.connect(self.id_to_puuid)

        btn_puuid_to_id = QPushButton("PUUID ➔ ID")
        btn_puuid_to_id.setStyleSheet(self.primary_button_style)
        btn_puuid_to_id.clicked.connect(self.puuid_to_id)
        
        btn_history = QPushButton("履歴を見る")
        btn_history.setStyleSheet(self.button_style)
        btn_history.clicked.connect(self.show_history)

        btn_close = QPushButton("閉じる")
        btn_close.setStyleSheet(self.button_style)
        btn_close.clicked.connect(self.reject)

        self.layout.addWidget(self.input_id)
        self.layout.addWidget(btn_id_to_puuid)
        self.layout.addWidget(self.input_puuid)
        self.layout.addWidget(btn_puuid_to_id)
        self.layout.addWidget(btn_history)
        self.layout.addWidget(btn_close)

    def id_to_puuid(self):
        api_key = get_api_key()
        riot_id = self.input_id.text().strip()
        
        if not api_key:
            print("[エラー] APIキーが読み込めません。.envファイルを確認してください。")
            return
        if not riot_id or "#" not in riot_id:
            print("[エラー] Riot IDの形式(Name#TAG)が不正です。")
            return
            
        print(f"\n[診断] === ID ➔ PUUID 変換処理開始 ===")
        print(f"[診断] 対象Riot ID: {riot_id}")
        
        name, tag = riot_id.split("#", 1)
        url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
        
        try:
            res = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=3)
            print(f"[診断] APIステータスコード: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                puuid = data.get("puuid", "")
                self.input_puuid.setText(puuid)
                self.main_app.save_puuid_history(riot_id, puuid)
                print("[成功] PUUIDを取得しました。")
            elif res.status_code == 403 or res.status_code == 401:
                print("[エラー] APIキーの期限が切れているか、権限がありません (401/403)。")
            elif res.status_code == 404:
                print("[エラー] 指定されたRiot IDが見つかりません (404 Not Found)。")
            else:
                print(f"[エラー] 未知のAPIエラーが発生しました。")
        except Exception as e:
            print(f"[エラー] 通信エラー: {e}")

    def puuid_to_id(self):
        api_key = get_api_key()
        puuid = self.input_puuid.text().strip()
        
        if not api_key:
            print("[エラー] APIキーが読み込めません。.envファイルを確認してください。")
            return
        if not puuid:
            print("[エラー] PUUIDが入力されていません。")
            return
            
        print(f"\n[診断] === PUUID ➔ ID 変換処理開始 ===")
        print(f"[診断] 対象PUUID: {puuid}")
            
        url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
        
        try:
            res = requests.get(url, headers={"X-Riot-Token": api_key}, timeout=3)
            print(f"[診断] APIステータスコード: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                riot_id = f"{data.get('gameName', '')}#{data.get('tagLine', '')}"
                self.input_id.setText(riot_id)
                self.main_app.save_puuid_history(riot_id, puuid)
                print("[成功] Riot IDを取得しました。")
            elif res.status_code == 403 or res.status_code == 401:
                print("[エラー] APIキーの期限が切れているか、権限がありません (401/403)。")
            elif res.status_code == 404:
                print("[エラー] 指定されたPUUIDが見つかりません (404 Not Found)。")
            else:
                print(f"[エラー] 未知のAPIエラーが発生しました。")
        except Exception as e:
            print(f"[エラー] 通信エラー: {e}")

    def show_history(self):
        history_dialog = PuuidHistoryDialog(self.main_app, self)
        history_dialog.exec()


class PuuidHistoryDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PUUID履歴")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #2b2d31; color: white;")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background-color: #1e1f22; color: #dbdee1; border: none;")
        
        settings = main_app.load_settings()
        history = settings.get("puuid_history", {})
        
        for riot_id, puuid in history.items():
            self.list_widget.addItem(f"{riot_id}\n{puuid}\n")
            
        layout.addWidget(self.list_widget)


class SideFormPanel(BaseSidePanel):
    def __init__(self, title, initial_id="", initial_pw="", parent=None):
        super().__init__(parent)
        self.auto_close = False
        self.add_title(title)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("RiotログインID")
        self.input_id.setText(initial_id)
        self.input_id.setStyleSheet(self.input_style)

        self.input_pw = QLineEdit()
        self.input_pw.setPlaceholderText("パスワード")
        self.input_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pw.setText(initial_pw)
        self.input_pw.setStyleSheet(self.input_style)

        btn_save = QPushButton("保存")
        btn_save.setStyleSheet(self.primary_button_style)
        btn_save.clicked.connect(self.accept)

        btn_cancel = QPushButton("キャンセル")
        btn_cancel.setStyleSheet(self.button_style)
        btn_cancel.clicked.connect(self.reject)

        self.layout.addWidget(self.input_id)
        self.layout.addWidget(self.input_pw)
        self.layout.addWidget(btn_save)
        self.layout.addWidget(btn_cancel)


class CustomMenu(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.keep_open = False
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)

        self.button_style = """
            QPushButton {
                background-color: transparent;
                color: white;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: bold;
                text-align: left;
                padding: 8px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #3f4147;
            }
        """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2b2d31"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 8, 8)

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def add_title(self, text):
        title = QLabel(text)
        title.setStyleSheet("color: #b5bac1; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: bold; padding: 4px 8px;")
        self.layout.addWidget(title)

    def add_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #3f4147;")
        self.layout.addWidget(line)

    def focusOutEvent(self, event):
        if not self.keep_open:
            self.hide()

    def on_account_right_clicked(self, account_name):
        self.keep_open = True
        action_panel = SideActionPanel(account_name, self)
        action_panel.move_beside(self)
        action_panel.exec()
        
        if action_panel.action_result == 'edit':
            self.show_edit_form(account_name)
        elif action_panel.action_result == 'delete':
            self.main_app.delete_account(account_name)
            self.show_menu("left")
        else:
            self.keep_open = False
            if not self.isActiveWindow():
                self.hide()

    def show_edit_form(self, account_name):
        settings = self.main_app.load_settings()
        creds = settings.get("login_accounts", {}).get(account_name, {})
        initial_id = creds.get("username", "")
        initial_pw = creds.get("password", "")

        form_panel = SideFormPanel(f"{account_name} の編集", initial_id, initial_pw, self)
        form_panel.move_beside(self)
        
        if form_panel.exec() == QDialog.DialogCode.Accepted:
            new_id = form_panel.input_id.text().strip()
            new_pw = form_panel.input_pw.text().strip()
            if new_id and new_pw:
                self.main_app.update_account_credentials(account_name, new_id, new_pw)
        
        self.keep_open = False
        self.show_menu("left")
        if not self.isActiveWindow():
            self.hide()

    def on_add_account_clicked(self):
        self.keep_open = True
        form_panel = SideFormPanel("新規アカウント登録", "", "", self)
        form_panel.move_beside(self)
        
        if form_panel.exec() == QDialog.DialogCode.Accepted:
            login_id = form_panel.input_id.text().strip()
            password = form_panel.input_pw.text().strip()
            if login_id and password:
                self.main_app.execute_add_account(login_id, password)
        
        self.keep_open = False
        self.hide()

    def on_puuid_tool_clicked(self):
        self.keep_open = True
        puuid_panel = SidePuuidPanel("", self.main_app, self)
        puuid_panel.move_beside(self)
        puuid_panel.exec()
        
        self.keep_open = False
        self.hide()

    def show_menu(self, mode):
        self.clear_layout()
        settings = self.main_app.load_settings()

        if mode == "left":
            self.add_title("LOGIN ACCOUNTS")
            accounts = settings.get("login_accounts", {})
            if isinstance(accounts, list):
                accounts = {}
            
            active_accounts = {k: v for k, v in accounts.items() if not v.get("deleted")}
                
            if not active_accounts:
                btn = QPushButton("アカウントがありません")
                btn.setStyleSheet(self.button_style)
                btn.setEnabled(False)
                self.layout.addWidget(btn)
            else:
                for acc, details in active_accounts.items():
                    display_text = acc
                    rank_cache = details.get("rank_cache")
                    if rank_cache and rank_cache.get("tier"):
                        tier_str = rank_cache.get("tier")
                        if tier_str.upper() == "UNRANKED":
                            tier_str = "un"
                        display_text = f"{acc} ({tier_str})"
                        
                    btn = AccountButton(display_text, acc)
                    btn.setStyleSheet(self.button_style)
                    btn.leftClicked.connect(self.main_app.switch_account)
                    btn.rightClicked.connect(self.on_account_right_clicked)
                    self.layout.addWidget(btn)
            
            self.add_separator()
            btn_add = QPushButton("[+] アカウントを追加")
            btn_add.setStyleSheet(self.button_style + "QPushButton { color: #5865F2; }")
            btn_add.clicked.connect(self.on_add_account_clicked)
            self.layout.addWidget(btn_add)

        else:
            self.add_title("MENU")

            btn_puuid = QPushButton("PUUIDツール")
            btn_puuid.setStyleSheet(self.button_style)
            btn_puuid.clicked.connect(self.on_puuid_tool_clicked)
            
            btn_settings = QPushButton("設定 (メモ帳)")
            btn_settings.setStyleSheet(self.button_style)
            btn_settings.clicked.connect(self.main_app.open_settings)
            
            btn_exit = QPushButton("終了")
            btn_exit.setStyleSheet(self.button_style)
            btn_exit.clicked.connect(self.main_app.quit_app)

            self.layout.addWidget(btn_puuid)
            self.layout.addWidget(btn_settings)
            self.layout.addWidget(btn_exit)

        self.adjustSize()
        pos = QCursor.pos()
        x = pos.x() - (self.width() // 2)
        y = pos.y() - self.height() - 15
        self.move(x, y)
        
        self.show()
        self.activateWindow()


class TrayApp:
    def __init__(self, app_instance):
        self.app = app_instance
        self.app.setQuitOnLastWindowClosed(False)
        
        self.setup_paths()
        self.menu = CustomMenu(self)
        self.launcher_thread = None
        self.rank_thread = None
        
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.get_tray_icon())
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def get_tray_icon(self):
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
            
        return self.create_svg_icon()

    def setup_paths(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        if not os.path.exists(SETTINGS_FILE):
            self.save_settings({
                "riot_client_path": "",
                "macro_trigger_key": "enter",
                "puuid_history": {},
                "login_accounts": {}
            })

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"riot_client_path": "", "macro_trigger_key": "enter", "puuid_history": {}, "login_accounts": {}}

    def save_settings(self, data):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[エラー] 設定ファイルの保存に失敗: {e}")

    def save_puuid_history(self, riot_id, puuid):
        settings = self.load_settings()
        history = settings.get("puuid_history", {})
        history[riot_id] = puuid
        settings["puuid_history"] = history
        self.save_settings(settings)

    def trigger_rank_updates(self):
        api_key = get_api_key()
        if not api_key:
            return
            
        settings = self.load_settings()
        accounts = settings.get("login_accounts", {})
        active_accounts = {k: v for k, v in accounts.items() if not v.get("deleted")}
        
        accounts_to_update = []
        current_time = time.time()
        
        for acc, details in active_accounts.items():
            rank_cache = details.get("rank_cache", {})
            updated_at = rank_cache.get("updated_at", 0)
            
            if current_time - updated_at > 86400:
                accounts_to_update.append(acc)
                
        if accounts_to_update:
            self.rank_thread = RankFetchThread(accounts_to_update, api_key)
            self.rank_thread.rank_fetched.connect(self.on_rank_fetched)
            self.rank_thread.start()

    def on_rank_fetched(self, account_name, tier):
        settings = self.load_settings()
        if account_name in settings.get("login_accounts", {}):
            settings["login_accounts"][account_name]["rank_cache"] = {
                "tier": tier,
                "updated_at": time.time()
            }
            self.save_settings(settings)
            
            if self.menu.isVisible():
                self.menu.show_menu("left")

    def get_riot_client_path(self):
        settings = self.load_settings()
        manual_path = settings.get("riot_client_path", "")
        if manual_path and os.path.exists(manual_path):
            return manual_path

        program_data = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
        installs_file = os.path.join(program_data, "Riot Games", "RiotClientInstalls.json")
        
        if os.path.exists(installs_file):
            try:
                with open(installs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    auto_path = data.get("rc_default", "")
                    if auto_path and os.path.exists(auto_path):
                        return auto_path
            except:
                pass
        return "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"

    def get_current_riot_id(self):
        lockfile_path = os.path.join(RIOT_CLIENT_DIR, "Config", "lockfile")
        if not os.path.exists(lockfile_path):
            return None
        
        try:
            with open(lockfile_path, 'r', encoding='utf-8') as f:
                data = f.read().split(':')
            
            if len(data) < 5:
                return None
                
            port = data[2]
            password = data[3]
            url = f"https://127.0.0.1:{port}/chat/v1/session"
            
            response = requests.get(url, auth=('riot', password), verify=False, timeout=3)
            if response.status_code == 200:
                json_data = response.json()
                game_name = json_data.get('game_name', '')
                game_tag = json_data.get('game_tag', '')
                
                if game_name and game_tag:
                    safe_name = f"{game_name}#{game_tag}".replace("/", "_").replace("\\", "_")
                    return safe_name
        except:
            pass
        return None

    def create_svg_icon(self):
        svg_data = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <rect width="100" height="100" rx="20" fill="#5865F2" />
            <circle cx="50" cy="50" r="25" fill="#FFFFFF" />
        </svg>'''
        renderer = QSvgRenderer(QByteArray(svg_data))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.trigger_rank_updates()
            self.menu.show_menu("left")
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.menu.show_menu("right")

    def kill_riot_processes(self):
        print("[処理] プロセスを強制終了中...")
        processes = [
            "RiotClientServices.exe", "RiotClientUx.exe",
            "LeagueClient.exe", "LeagueClientUx.exe",
            "RiotClientCrashHandler.exe", "LeagueCrashHandler.exe"
        ]
        for p in processes:
            subprocess.run(["taskkill", "/F", "/IM", p, "/T"], capture_output=True, creationflags=CREATE_NO_WINDOW)
        time.sleep(1.0) 

    def update_account_credentials(self, account_name, login_id, password):
        settings = self.load_settings()
        if "login_accounts" in settings and account_name in settings["login_accounts"]:
            settings["login_accounts"][account_name]["username"] = login_id
            settings["login_accounts"][account_name]["password"] = password
            self.save_settings(settings)
            print(f"[情報] {account_name} のログイン情報を更新しました。")

    def delete_account(self, account_name):
        settings = self.load_settings()
        if "login_accounts" in settings and account_name in settings["login_accounts"]:
            settings["login_accounts"][account_name]["deleted"] = True
            self.save_settings(settings)
            print(f"[情報] アカウント '{account_name}' を論理削除しました。")

    def check_session_via_api(self):
        print("  -> ローカルAPIによる認証状態の確認を開始します (最大3秒待機)...")
        for _ in range(15): 
            time.sleep(0.2)
            lockfile_path = os.path.join(RIOT_CLIENT_DIR, "Config", "lockfile")
            if not os.path.exists(lockfile_path):
                continue
                
            try:
                with open(lockfile_path, 'r', encoding='utf-8') as f:
                    data = f.read().split(':')
                
                if len(data) < 5:
                    continue
                    
                port = data[2]
                password = data[3]
                url = f"https://127.0.0.1:{port}/chat/v1/session"
                
                response = requests.get(url, auth=('riot', password), verify=False, timeout=1)
                if response.status_code == 200:
                    json_data = response.json()
                    if json_data.get('game_name'):
                        return True
            except:
                pass
                
        return False

    def launch_lol_with_retry(self):
        exe_path = self.get_riot_client_path()
        if not os.path.exists(exe_path):
            print("[エラー] 実行ファイルが見つかりません。")
            return
        
        self.launcher_thread = LolLauncherThread(exe_path, RIOT_CLIENT_DIR)
        self.launcher_thread.start()

    def execute_add_account(self, login_id, password):
        print("\n[開始] アカウントの新規追加フローを開始します。")
        self.kill_riot_processes()
        
        token_path = os.path.join(RIOT_CLIENT_DIR, "Data", "RiotGamesPrivateSettings.yaml")
        if os.path.exists(token_path):
            os.remove(token_path)
            print("  -> 現在のセッション(トークン)を物理削除しました。")
        
        exe_path = self.get_riot_client_path()
        if os.path.exists(exe_path):
            subprocess.Popen([exe_path])
            
        direct_creds = {"username": login_id, "password": password}
        self.execute_macro(account_name=None, direct_creds=direct_creds)

    def execute_macro(self, account_name=None, direct_creds=None):
        settings = self.load_settings()
        
        if direct_creds:
            creds = direct_creds
        else:
            creds = settings.get("login_accounts", {}).get(account_name)
            
        if not creds:
            print("[エラー] 自動入力用のクレデンシャル情報がありません。")
            return

        trigger_key = settings.get("macro_trigger_key", "enter")

        print("  -> Riot Clientの起動とウィンドウを待機中...")
        hwnd = None
        for _ in range(30): 
            hwnd = win32gui.FindWindow(None, "Riot Client")
            if hwnd:
                break
            time.sleep(0.1)
            
        if not hwnd:
            print("[エラー] ウィンドウが見つかりませんでした。マクロを中止します。")
            return
            
        print(f"\n=======================================================")
        print(f" [待機中] 画面が読み込まれ、入力可能状態になったら")
        print(f" キーボードの 『 {trigger_key.upper()} 』 キーを押してください。")
        print(f"=======================================================\n")
        
        keyboard.wait(trigger_key)
        print("  -> キー入力を検知しました。マクロを開始します...")
        
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass
            
        time.sleep(0.2)
        
        name_for_print = account_name if account_name else "新規アカウント"
        print(f"[マクロ] {name_for_print} の情報を自動入力中...")
        pyautogui.write(creds["username"])
        pyautogui.press('tab')
        pyautogui.write(creds["password"])
        pyautogui.press('tab', presses=6, interval=0.05)
        pyautogui.press('enter')
        time.sleep(0.1)
        pyautogui.press('tab')
        time.sleep(0.1)
        pyautogui.press('enter')
        print("[成功] マクロ入力を完了しました。")

        print("  -> ログインの完了を待機中...")
        riot_id = None
        for _ in range(30):
            time.sleep(0.5)
            riot_id = self.get_current_riot_id()
            if riot_id:
                break
                
        if not riot_id:
            print("[エラー] ログインの完了を確認できませんでした。保存を中止します。")
            return
            
        token_path = os.path.join(RIOT_CLIENT_DIR, "Data", "RiotGamesPrivateSettings.yaml")
        if not os.path.exists(token_path) or os.path.getsize(token_path) < 1000:
            print("[エラー] ログインが完了していません（空のセッション）。保存を中止します。")
            return

        print(f"[成功] ログインを確認しました: {riot_id}")
        print("  -> 新しいセッション情報を自動保存します...")
        
        target_dir = os.path.join(PROFILES_DIR, riot_id)
        try:
            os.makedirs(target_dir, exist_ok=True)
            for f_def in FILES_TO_SWITCH:
                src = os.path.join(RIOT_CLIENT_DIR, os.path.normpath(f_def["rel_path"]))
                dst = os.path.join(target_dir, f_def["filename"])
                if f_def["is_dir"]:
                    if os.path.exists(dst): shutil.rmtree(dst)
                    if os.path.exists(src): shutil.copytree(src, dst)
                else:
                    if os.path.exists(src):
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)

            settings = self.load_settings()
            accounts = settings.get("login_accounts", {})
            accounts[riot_id] = creds
            
            if account_name and riot_id != account_name and account_name in accounts:
                del accounts[account_name]
                old_dir = os.path.join(PROFILES_DIR, account_name)
                if os.path.exists(old_dir):
                    shutil.rmtree(old_dir, ignore_errors=True)
                    
            settings["login_accounts"] = accounts
            self.save_settings(settings)
            print(f"[成功] {riot_id} としてセッションを自動保存しました。")
        except Exception as e:
            print(f"[エラー] セッションの自動保存に失敗しました: {e}")

        print("  -> League of Legends の自動起動を開始します...")
        self.launch_lol_with_retry()

    def switch_account(self, account_name):
        self.menu.hide()
        print(f"\n[開始] {account_name} に切り替えます。")
        self.kill_riot_processes()

        target_dir = os.path.join(PROFILES_DIR, account_name)
        has_profile = os.path.exists(target_dir)

        if has_profile:
            try:
                for f_def in FILES_TO_SWITCH:
                    src = os.path.join(target_dir, f_def["filename"])
                    dst = os.path.join(RIOT_CLIENT_DIR, os.path.normpath(f_def["rel_path"]))
                    if f_def["is_dir"]:
                        if os.path.exists(dst): shutil.rmtree(dst)
                        if os.path.exists(src): shutil.copytree(src, dst)
                    else:
                        if os.path.exists(src):
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(src, dst)
            except Exception as e:
                print(f"[エラー] ファイル入れ替え中にエラー: {e}")
                return

            exe_path = self.get_riot_client_path()
            if os.path.exists(exe_path):
                subprocess.Popen([exe_path])
                
                if not self.check_session_via_api():
                    print("[警告] APIからの認証情報取得に失敗。セッションが無効化されています！")
                    print("  -> 無効なバックアップを破棄し、すでに出現しているログイン画面でマクロを実行します。")
                    shutil.rmtree(target_dir, ignore_errors=True)
                    
                    token_path = os.path.join(RIOT_CLIENT_DIR, "Data", "RiotGamesPrivateSettings.yaml")
                    if os.path.exists(token_path):
                        os.remove(token_path)
                    
                    self.execute_macro(account_name)
                else:
                    print(f"[成功] {account_name} へのファイル切り替えと認証が完了しました。")
                    print("  -> League of Legends の自動起動を開始します...")
                    self.launch_lol_with_retry()
        else:
            print("[情報] プロファイルが存在しないため、マクロログインを試みます。")
            token_path = os.path.join(RIOT_CLIENT_DIR, "Data", "RiotGamesPrivateSettings.yaml")
            if os.path.exists(token_path):
                os.remove(token_path)
            
            exe_path = self.get_riot_client_path()
            if os.path.exists(exe_path):
                subprocess.Popen([exe_path])
            self.execute_macro(account_name)

    def open_settings(self):
        self.menu.hide()
        os.startfile(SETTINGS_FILE)

    def quit_app(self):
        self.menu.hide()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    shared_mem = QSharedMemory("LoL_Account_Switcher_Unique_Key")
    if not shared_mem.create(1):
        print("[情報] 既にアプリケーションが起動しているため、新しいプロセスを終了します。")
        sys.exit(0)
        
    app_instance = TrayApp(app)
    app_instance.run()