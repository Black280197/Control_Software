import os
import psutil
import time
import datetime
import win32gui
import win32process
import logging
import pyautogui
from pywinauto import Application
import mss
import socket
import platform
import subprocess
import netifaces
import sys
import json
import tkinter as tk
import threading

# Đường dẫn thư mục chứa file cấu hình trên mạng
CONFIG_PATH = os.path.normpath(r"\\10.0.0.125\9.2. dùng chung\3. ERP-KPI-TRIEN KHAI\ERP_Manager\Check New App")
LOG_FILE_PATH = None
LOG_BLOCK = None
LOG_APPS = None

# Thêm biến toàn cục cho logging
LOGGING_DIR = None  # Thư mục loggingOfApp
ERROR_LOG = None    # File error.log
OPERATION_LOG = None  # File operation.log

# Hàm kiểm tra single instance bằng socket
def check_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("localhost", 9999))  # Thử bind vào cổng 9999
        return s  # Trả về socket nếu bind thành công (chưa có instance nào chạy)
    except socket.error:
        sys.exit(1)  # Thoát nếu đã có instance khác chạy

def get_system_info():
    """Lấy thông tin MAC và IP của máy tính"""
    try:
        mac = ""
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            addr = netifaces.ifaddresses(interface)
            if netifaces.AF_LINK in addr:
                if addr[netifaces.AF_LINK][0]['addr']:
                    mac = addr[netifaces.AF_LINK][0]['addr']
                    log_operation(f"Đã tìm thấy MAC address: {mac} trên interface {interface}")
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        log_operation(f"Thông tin hệ thống - Hostname: {hostname}, IP: {ip}")
        return mac, ip
    except Exception as e:
        log_error(f"Lỗi khi lấy thông tin hệ thống: {str(e)}")
        return None, None

def log_system_info():
    """Ghi log thông tin MAC và IP vào file Phan_quyen.txt"""
    try:
        global mac, ip
        mac, ip = get_system_info()
        if mac and ip:
            global MAC_DIR
            MAC_DIR = os.path.join(CONFIG_PATH, "LOG", mac.replace(":", "_"))
            if not os.path.exists(MAC_DIR):
                os.makedirs(MAC_DIR)
                log_operation(f"Đã tạo thư mục MAC: {MAC_DIR}")

            global LOG_FILE_PATH, LOG_BLOCK, LOG_APPS
            LOG_FILE_PATH = os.path.join(MAC_DIR, "Log_HIS.txt")
            LOG_BLOCK = os.path.join(MAC_DIR, "Log_BLOCK.txt")
            LOG_APPS = os.path.join(MAC_DIR, "Log_APPS.txt")
            log_file = os.path.join(MAC_DIR, "Permission.txt")
            group_roles_file = os.path.join(CONFIG_PATH, "Group_Roles.txt")
            data = {}
            if os.path.exists(log_file):
                if os.path.getsize(log_file) > 0:
                    try:
                        with open(log_file, "r", encoding='utf-8') as f:
                            data = json.load(f)
                    except json.JSONDecodeError:
                        log_operation(f"File {log_file} không chứa JSON hợp lệ, khởi tạo dữ liệu mới.")
                        data = {}
                else:
                    log_operation(f"File {log_file} rỗng, khởi tạo dữ liệu mới.")
                    data = {}
            else:
                log_operation(f"File {log_file} không tồn tại, tạo file mới.")
            mac_clone = mac.replace(":", "_")
            if mac_clone not in data:
                data[mac_clone] = {
                    "ip": ip,
                    "Computer_Name": platform.node(),
                    "Group_Roles": "P_FREE",
                    "Name_Users": "Anonimous",
                    "Shot_Ready": 0,
                    "Shot_Enable": 0,
                    "Last_Seen": datetime.datetime.now().isoformat()
                }
            else:
                if "ip" not in data[mac_clone]:
                    data[mac_clone]["ip"] = ip
                if "Computer_Name" not in data[mac_clone]:
                    data[mac_clone]["Computer_Name"] = platform.node()
                if "Group_Roles" not in data[mac_clone]:
                    data[mac_clone]["Group_Roles"] = "P_FREE"
                if "Shot_Ready" not in data[mac_clone]:
                    data[mac_clone]["Shot_Ready"] = 0
                if "Shot_Enable" not in data[mac_clone]:
                    data[mac_clone]["Shot_Enable"] = 0
                data[mac_clone]["Last_Seen"] = datetime.datetime.now().isoformat()

            with open(log_file, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log_operation(f"Đã cập nhật thông tin hệ thống cho MAC {mac_clone}")
                
            global myObject
            myObject = data[mac_clone]
            log_operation(f"Đã khởi tạo cấu hình cho người dùng: {myObject.get('Name_Users', 'Anonymous')}")
            
            default_group_roles = {
                "P_ERP": {
                    "block_times": ["07:30-11:45", "12:45-17:00"],
                    "block_apps": ["Zalo.exe", "Discord.exe"],
                    "block_sites": ["facebook", "zalo", "messenger"],
                    "enable_blocking": 0,
                    "blocked_domains": ["www.facebook.com", "facebook.com", "m.facebook.com", "web.facebook.com"],
                    "redirect_page": "http://10.0.0.3:8009/"
                },
                "P_FREE": {
                    "block_times": [],
                    "block_apps": [],
                    "block_sites": [],
                    "enable_blocking": 0,
                    "blocked_domains": [],
                    "redirect_page": "http://10.0.0.3:8009/"
                }
            }
            
            group_roles_data = default_group_roles
            
            if os.path.exists(group_roles_file):
                try:
                    if os.path.getsize(group_roles_file) > 0:
                        with open(group_roles_file, "r", encoding='utf-8') as f:
                            file_data = json.load(f)
                            if file_data:
                                group_roles_data = file_data
                            else:
                                log_operation(f"File {group_roles_file} rỗng, sử dụng cấu hình mặc định")
                    else:
                        log_operation(f"File {group_roles_file} rỗng, sử dụng cấu hình mặc định")
                except (json.JSONDecodeError, PermissionError) as e:
                    log_operation(f"Lỗi đọc file Group_Roles.txt: {str(e)}, sử dụng cấu hình mặc định")
            else:
                log_operation("File Group_Roles.txt không tồn tại, sử dụng cấu hình mặc định")
            
            global myConfig
            myConfig = group_roles_data.get(myObject["Group_Roles"], default_group_roles["P_FREE"])
            log_operation(f"Đã áp dụng cấu hình Group_Roles: {myObject['Group_Roles']}")
            
    except Exception as e:
        log_error(f"Lỗi ghi log thông tin hệ thống: {str(e)}")

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

def get_config_value(field_name, default_value):
    try:
        value = myConfig.get(field_name)
        return value if value is not None else default_value
    except:
        return default_value
    
def get_my_setting_value(field_name, default_value):
    try:
        value = myObject.get(field_name)
        return value if value is not None else default_value
    except:
        return default_value

def load_list_from_file(filename, default_list):
    file_path = os.path.join(CONFIG_PATH, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            log_error(f"Lỗi đọc file {filename}: {str(e)}")
    return default_list

BROWSERS, BLOCKED_APPS, BLOCKED_SITES, BLOCK_TIME_RANGES = [], [], [], []
ENABLE_BLOCKING = 0
REDIRECT_URL = "http://10.0.0.3:8009/"
BLOCK_TIME_RANGES = ["00:00-23:59"]

def update_blocked_lists():
    try:
        global BROWSERS, BLOCKED_APPS, BLOCKED_SITES, BLOCK_TIME_RANGES, ENABLE_BLOCKING, REDIRECT_URL
        BROWSERS = load_list_from_file("browsers.txt", [])
        BLOCKED_APPS = get_config_value("block_apps", [])
        BLOCKED_SITES = get_config_value("block_sites", [])
        BLOCK_TIME_RANGES = get_config_value("block_times", [])
        ENABLE_BLOCKING = get_config_value("enable_blocking", 0)
        REDIRECT_URL = get_config_value("redirect_page", "http://10.0.0.3:8009/")
        log_operation("Đã cập nhật danh sách chặn từ cấu hình")
    except Exception as e:
        log_error(f"Lỗi cập nhật danh sách chặn: {str(e)}")

def is_block_time():
    try:
        now = datetime.datetime.now().time()
        for time_range in BLOCK_TIME_RANGES:
            start, end = time_range.split("-")
            start_time = datetime.datetime.strptime(start, "%H:%M").time()
            end_time = datetime.datetime.strptime(end, "%H:%M").time()
            if start_time <= now <= end_time:
                return True
        return False
    except Exception as e:
        log_error(f"Lỗi kiểm tra thời gian chặn: {str(e)}")
        return False

def get_browser_info():
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        if proc.name().lower() in BROWSERS:
            title = win32gui.GetWindowText(hwnd).lower()
            app = Application(backend="uia").connect(process=pid, timeout=1)
            dlg = app.top_window()
            url = dlg.child_window(title_re=".*", control_type="Edit").get_value().lower()
            return title, url, hwnd
    except:
        return "", "", None
    return "", "", None

def log_visited_url(url):
    try:
        if not os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("Danh sách các URL đã truy cập:\n")
        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            logged_urls = f.readlines()
        if url + "\n" not in logged_urls:
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(url + "\n\n")
    except Exception as e:
        log_error(f"Lỗi ghi log URL: {str(e)}")

def log_blocked_url(url):
    try:
        with open(LOG_BLOCK, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} - URL bị chặn: {url}\n")
    except Exception as e:
        log_error(f"Lỗi ghi log URL bị chặn: {str(e)}")

def log_running_apps():
    try:
        running_apps = {proc.name(): datetime.datetime.now() for proc in psutil.process_iter(attrs=['name'])}
        app_logs = {}
        if os.path.exists(LOG_APPS):
            with open(LOG_APPS, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    try:
                        parts = line.strip().split(" - ")
                        if len(parts) == 2:
                            timestamp_str, app_name = parts
                            timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                            app_logs[app_name] = timestamp
                    except:
                        continue
        app_logs.update(running_apps)
        with open(LOG_APPS, "w", encoding="utf-8") as f:
            for app_name, timestamp in app_logs.items():
                f.write(f"{timestamp} - {app_name}\n")
    except Exception as e:
        log_error(f"Lỗi ghi log ứng dụng đang chạy: {str(e)}")

def take_screenshot():
    if get_my_setting_value("Shot_Enable", 0) == 0:
        return
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with mss.mss() as sct:
            for i, monitor in enumerate(sct.monitors[1:], 1):
                screenshot = sct.grab(monitor)
                mss.tools.to_png(screenshot.rgb, screenshot.size, 
                               output=os.path.join(SCREENSHOT_PATH, f"screenshot_{timestamp}_monitor_{i}.png"))
        log_file = os.path.join(MAC_DIR, "Permission.txt")
        try:
            with open(log_file, "r", encoding='utf-8') as f:
                data = json.load(f)
            if mac in data:
                data[mac]["Shot_Ready"] = 0
                with open(log_file, "w", encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                log_operation("Đã cập nhật Shot_Ready = 0 trong Phan_quyen.txt")
        except Exception as e:
            log_operation(f"Lỗi khi cập nhật Shot_Ready trong Phan_quyen.txt: {str(e)}")
        log_operation("Đã chụp ảnh tất cả màn hình")
    except Exception as e:
        log_operation(f"Lỗi chụp ảnh màn hình: {str(e)}")

def close_tab(hwnd):
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "w")
    except:
        pass

def open_redirect_page(hwnd):
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.5)
        redirect_url = f"{REDIRECT_URL}?name={myObject.get('Computer_Name', 'Anonymous')}"
        pyautogui.typewrite(redirect_url)
        pyautogui.press("enter")
    except:
        pass

def kill_blocked_apps():
    for proc in psutil.process_iter():
        try:
            if proc.name() in BLOCKED_APPS:
                take_screenshot()
                show_warning_popup("app", proc.name())
                proc.kill()
                log_operation(f"Đã đóng ứng dụng bị chặn: {proc.name()}")
        except Exception as e:
            log_error(f"Lỗi khi đóng ứng dụng {proc.name()}: {str(e)}")

def show_warning_popup(violation_type, details):
    def show_message():
        try:
            root = tk.Tk()
            root.withdraw()
            top = tk.Toplevel(root)
            top.overrideredirect(True)
            top.geometry("500x300")
            top.resizable(False, False)
            top.attributes('-topmost', True)
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width - 500) // 2
            y = (screen_height - 300) // 2
            top.geometry(f"500x300+{x}+{y}")
            frame = tk.Frame(
                top,
                bg="#8B0000",
                highlightbackground="#FF4500",
                highlightthickness=4,
                borderwidth=2,
                relief="groove"
            )
            frame.pack(fill="both", expand=True, padx=5, pady=5)
            title_bar = tk.Frame(frame, bg="#FF4500", height=20)
            title_bar.pack(fill="x")
            close_button = tk.Button(
                title_bar,
                text="X",
                command=top.destroy,
                font=('Arial', 12, 'bold'),
                bg="#FF4500",
                fg="white",
                relief="flat",
                width=2,
                height=1,
                pady=0,
                padx=0
            )
            close_button.pack(side="right")
            canvas = tk.Canvas(frame, bg="#8B0000")
            scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview, bg="#FF4500")
            scrollable_frame = tk.Frame(canvas, bg="#8B0000")
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            warning_message = f"""CẢNH BÁO VI PHẠM!
            
Loại vi phạm: {'Website' if violation_type == 'web' else 'Ứng dụng'}

Chi tiết: {("Truy cập link " + details) if violation_type == 'web' else ("Truy cập ứng dụng " + details)}

Thời gian: {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

Người dùng: {myObject.get('Computer_Name', 'Anonymous')}            
Nghi vấn có hành vi truy cập vào trang web hoặc ứng dụng không có trong danh sách được cho phép!"""
            label = tk.Label(
                scrollable_frame,
                text=warning_message,
                font=('Arial', 14, 'bold'),
                fg="white",
                justify="left",
                wraplength=460,
                bg="#8B0000"
            )
            label.pack(pady=10)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            top.after(20000, top.destroy)
            root.mainloop()
        except Exception as e:
            log_error(f"Lỗi hiển thị cảnh báo: {str(e)}")
    warning_thread = threading.Thread(target=show_message)
    warning_thread.daemon = True
    warning_thread.start()

counter = 0

def check_and_update_hosts():
    try:
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        if not os.path.exists(hosts_path):
            log_error("Không tìm thấy file hosts")
            return
        blocked_domains = myConfig.get("blocked_domains", [])
        log_operation(f"Cập nhật file hosts với {len(blocked_domains)} domain bị chặn")
        try:
            with open(hosts_path, 'r', encoding='utf-8') as f:
                original_content = f.readlines()
            cleaned_content = []
            is_tool_block = False
            for line in original_content:
                if "# Blocked by monitoring tool" in line:
                    is_tool_block = True
                    continue
                if not is_tool_block:
                    cleaned_content.append(line)
                if line.strip() == "":
                    is_tool_block = False
            new_content = cleaned_content
            if blocked_domains:
                new_content.append("\n# Blocked by monitoring tool\n")
                for domain in blocked_domains:
                    new_content.append(f"127.0.0.1 {domain}\n")
            with open(hosts_path, 'w', encoding='utf-8') as f:
                f.writelines(new_content)
            log_operation("Đã cập nhật thành công file hosts")
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log_operation("Đã làm mới DNS cache")
        except PermissionError:
            log_error("Không có quyền ghi file hosts. Hãy chạy với quyền Administrator")
        except Exception as e:
            log_error(f"Lỗi khi ghi file hosts: {str(e)}")
    except Exception as e:
        log_error(f"Lỗi khi cập nhật file hosts: {str(e)}")

def clean_log_files():
    try:
        log_files = [LOG_FILE_PATH, LOG_BLOCK, LOG_APPS]
        for log_file in log_files:
            if log_file and os.path.exists(log_file):
                backup_dir = os.path.join(os.path.dirname(log_file), "backup")
                if not os.path.exists(backup_dir):
                    os.makedirs(backup_dir)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{os.path.basename(log_file)}_{timestamp}.bak"
                backup_file = os.path.join(backup_dir, backup_name)
                try:
                    with open(log_file, 'r', encoding='utf-8') as src:
                        with open(backup_file, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                    log_operation(f"Đã tạo backup cho file {log_file}")
                except Exception as e:
                    log_error(f"Lỗi khi tạo backup cho file {log_file}: {str(e)}")
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        if log_file == LOG_FILE_PATH:
                            f.write("Danh sách các URL đã truy cập:\n")
                        elif log_file == LOG_BLOCK:
                            f.write("Danh sách các URL bị chặn:\n")
                        elif log_file == LOG_APPS:
                            f.write("Danh sách các ứng dụng đã chạy:\n")
                    log_operation(f"Đã làm sạch file {log_file}")
                except Exception as e:
                    log_error(f"Lỗi khi làm sạch file {log_file}: {str(e)}")
    except Exception as e:
        log_error(f"Lỗi trong quá trình làm sạch log files: {str(e)}")

def cleanup_screenshots():
    try:
        if not os.path.exists(SCREENSHOT_PATH):
            return
        screenshots = []
        for file in os.listdir(SCREENSHOT_PATH):
            if file.startswith("screenshot_") and file.endswith(".png"):
                file_path = os.path.join(SCREENSHOT_PATH, file)
                creation_time = os.path.getctime(file_path)
                screenshots.append((file_path, creation_time))
        if len(screenshots) > 100:
            screenshots.sort(key=lambda x: x[1], reverse=True)
            files_to_delete = screenshots[50:]
            for file_path, _ in files_to_delete:
                try:
                    os.remove(file_path)
                    log_operation(f"Đã xóa ảnh cũ: {os.path.basename(file_path)}")
                except Exception as e:
                    log_error(f"Lỗi khi xóa file {file_path}: {str(e)}")
            log_operation(f"Đã xóa {len(files_to_delete)} ảnh cũ, giữ lại 50 ảnh mới nhất")
    except Exception as e:
        log_error(f"Lỗi trong quá trình dọn dẹp ảnh: {str(e)}")

def update_config_data():
    try:
        global myObject, myConfig
        permission_file = os.path.join(MAC_DIR, "Permission.txt")
        if os.path.exists(permission_file):
            try:
                with open(permission_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                if mac in data:
                    myObject = data[mac]
                    log_operation(f"Đã cập nhật thông tin người dùng: {myObject.get('Name_Users', 'Anonymous')}")
            except Exception as e:
                log_error(f"Lỗi đọc Permission.txt: {str(e)}")
        group_roles_file = os.path.join(CONFIG_PATH, "Group_Roles.txt")
        default_group_roles = {
            "P_ERP": {
                "block_times": ["07:30-11:45", "12:45-17:00"],
                "block_apps": ["Zalo.exe", "Discord.exe"],
                "block_sites": ["facebook", "zalo", "messenger"],
                "enable_blocking": 0,
                "blocked_domains": ["www.facebook.com", "facebook.com", "m.facebook.com", "web.facebook.com"],
                "redirect_page": "http://10.0.0.3:8009/"
            },
            "P_FREE": {
                "block_times": [],
                "block_apps": [],
                "block_sites": [],
                "enable_blocking": 0,
                "blocked_domains": [],
                "redirect_page": "http://10.0.0.3:8009/"
            }
        }
        if os.path.exists(group_roles_file):
            try:
                with open(group_roles_file, "r", encoding='utf-8') as f:
                    group_roles_data = json.load(f)
                if group_roles_data:
                    current_group = myObject.get("Group_Roles", "P_FREE")
                    myConfig = group_roles_data.get(current_group, default_group_roles["P_FREE"])
                    log_operation(f"Đã cập nhật cấu hình cho nhóm: {current_group}")
            except Exception as e:
                log_error(f"Lỗi đọc Group_Roles.txt: {str(e)}")
    except Exception as e:
        log_error(f"Lỗi cập nhật cấu hình: {str(e)}")

def update_last_seen():
    log_file = os.path.join(MAC_DIR, "Permission.txt")
    try:
        with open(log_file, "r", encoding='utf-8') as f:
            data = json.load(f)
        if mac in data:
            data[mac]["Last_Seen"] = datetime.datetime.now().isoformat()
            with open(log_file, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log_operation("Đã cập nhật Last_Seen trong Phan_quyen.txt")
    except Exception as e:
        log_error(f"Lỗi khi cập nhật Last_Seen trong Phan_quyen.txt: {str(e)}")

def setup_logging():
    global mac, ip
    mac, ip = get_system_info()
    if mac and ip:
        global MAC_DIR
        MAC_DIR = os.path.join(CONFIG_PATH, "LOG", mac.replace(":", "_"))
        if not os.path.exists(MAC_DIR):
            os.makedirs(MAC_DIR)
            log_operation(f"Đã tạo thư mục MAC: {MAC_DIR}")
    global LOGGING_DIR, ERROR_LOG, OPERATION_LOG
    LOGGING_DIR = os.path.join(MAC_DIR, "loggingOfApp")
    if not os.path.exists(LOGGING_DIR):
        os.makedirs(LOGGING_DIR)
    ERROR_LOG = os.path.join(LOGGING_DIR, "error.log")
    OPERATION_LOG = os.path.join(LOGGING_DIR, "operation.log")
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
    error_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    error_logger.addHandler(error_handler)
    operation_logger = logging.getLogger('operation_logger')
    operation_logger.setLevel(logging.INFO)
    operation_handler = logging.FileHandler(OPERATION_LOG, encoding='utf-8')
    operation_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    operation_logger.addHandler(operation_handler)

def log_error(message):
    error_logger = logging.getLogger('error_logger')
    error_logger.error(message)

def log_operation(message):
    operation_logger = logging.getLogger('operation_logger')
    operation_logger.info(message)

def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def run_as_admin():
    if not is_admin():
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            log_operation("Đã yêu cầu quyền admin")
            sys.exit(0)
        except Exception as e:
            log_error(f"Lỗi khi yêu cầu quyền admin: {str(e)}")
            sys.exit(1)

# Khởi tạo ứng dụng
sock = check_single_instance()  # Kiểm tra single instance trước khi chạy
setup_logging()
run_as_admin()
log_system_info()
clean_log_files()
update_last_seen()

SCREENSHOT_PATH = os.path.join(MAC_DIR, "screenShot")
if not os.path.exists(SCREENSHOT_PATH):
    os.makedirs(SCREENSHOT_PATH)

while True:
    try:
        if is_block_time():
            if counter % 15 == 0:
                update_config_data()
                update_blocked_lists()
                log_system_info()
            SHOT_READY = get_my_setting_value("Shot_Ready", 0)
            if SHOT_READY == 1:
                log_operation("Thực hiện chụp màn hình theo yêu cầu")
                take_screenshot()
            if counter % 150 == 0:
                log_operation(f"Thực hiện kiểm tra ứng dụng định kỳ vào lúc {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                log_running_apps()
                check_and_update_hosts()
            if counter % 450 == 0:
                log_operation(f"Cập nhật trạng thái hoạt động vào lúc {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                update_last_seen()
            title, url, browser_hwnd = get_browser_info()
            if url:
                log_visited_url(url)
            if any(site in url for site in BLOCKED_SITES) or any(tit in title for tit in BLOCKED_SITES):
                take_screenshot()
                if ENABLE_BLOCKING:
                    log_blocked_url(url)
                    close_tab(browser_hwnd)
                    show_warning_popup("web", url)
            if ENABLE_BLOCKING:
                kill_blocked_apps()
        counter += 1
        time.sleep(2)
    except Exception as e:
        log_error(f"Lỗi trong vòng lặp chính: {str(e)}")
        time.sleep(5)

# Đóng socket khi thoát (dù vòng lặp vô hạn sẽ không đến đây)
sock.close()

