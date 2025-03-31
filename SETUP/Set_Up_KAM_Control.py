import os
import json
import tkinter as tk
from tkinter import messagebox
import psutil
import netifaces
import subprocess
import shutil
import time
import logging
import sys
import winreg
import datetime
import platform
import socket
import win32com.client
import ctypes
import win32gui
import win32process
import pyautogui
from pywinauto import Application
from datetime import timedelta
import mss
import threading

# Đường dẫn mạng và startup
NETWORK_PATH = r"\\10.0.0.125\\9.2. dùng chung\\3. ERP-KPI-TRIEN KHAI\\ERP_Manager\\Check New App"
SOURCE_FILE_LC = os.path.join(NETWORK_PATH, "System_LC.exe")  # File System_LC.exe
SOURCE_FILE_UPDATER = os.path.join(NETWORK_PATH, "SystemLC_Updater.exe")  # File SystemLC_Updater.exe
STARTUP_PATH = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
TARGET_DIR = r"C:\Program Files\System_LC"  # Thư mục cố định để lưu file .exe
TARGET_FILE_LC = os.path.join(TARGET_DIR, "System_LC.exe")  # Đích cố định cho System_LC.exe
TARGET_FILE_UPDATER = os.path.join(TARGET_DIR, "SystemLC_Updater.exe")  # Đích cố định cho SystemLC_Updater.exe
LOG_PATH = os.path.join(NETWORK_PATH, "LOG")

# Thêm biến toàn cục cho logging
LOGGING_DIR = None  # Thư mục loggingOfApp
ERROR_LOG = None    # File error.log
OPERATION_LOG = None  # File operation.log

# Hàm kiểm tra single instance
def check_single_instance():
    """Kiểm tra xem đã có instance nào của ứng dụng đang chạy chưa"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("localhost", 9998))  # Sử dụng port khác với System_LC.py
        return s  # Trả về socket nếu bind thành công (chưa có instance nào chạy)
    except socket.error:
        sys.exit(1)  # Thoát nếu đã có instance khác chạy

# Thêm hàm setup_logging
def setup_logging():
    """Cấu hình logging cho error và operation"""
    global LOGGING_DIR, ERROR_LOG, OPERATION_LOG
    
    # Tạo thư mục loggingOfApp trong thư mục cài đặt
    mac_address = get_mac_address()
    log_dir = os.path.join(LOG_PATH, mac_address)
    os.makedirs(log_dir, exist_ok=True)
    LOGGING_DIR = os.path.join(log_dir, "loggingOfSetting")
    if not os.path.exists(LOGGING_DIR):
        os.makedirs(LOGGING_DIR)
    
    # Đường dẫn file log
    ERROR_LOG = os.path.join(LOGGING_DIR, "error.log")
    OPERATION_LOG = os.path.join(LOGGING_DIR, "operation.log")
    
    # Cấu hình logger cho error
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
    error_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    error_logger.addHandler(error_handler)
    
    # Cấu hình logger cho operation
    operation_logger = logging.getLogger('operation_logger')
    operation_logger.setLevel(logging.INFO)
    operation_handler = logging.FileHandler(OPERATION_LOG, encoding='utf-8')
    operation_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    operation_logger.addHandler(operation_handler)

# Thêm hàm log_error và log_operation
def log_error(message):
    """Ghi lỗi vào file error.log"""
    error_logger = logging.getLogger('error_logger')
    error_logger.error(message)

def log_operation(message):
    """Ghi thao tác vào file operation.log"""
    operation_logger = logging.getLogger('operation_logger')
    operation_logger.info(message)

# Hàm kiểm tra quyền admin
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

# Hàm yêu cầu quyền admin
def run_as_admin():
    if not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            log_operation("Đã yêu cầu quyền admin")
            sys.exit(0)
        except Exception as e:
            log_error(f"Lỗi khi yêu cầu quyền admin: {str(e)}")
            sys.exit(1)

# Hàm lấy địa chỉ MAC
def get_mac_address():
    """Lấy địa chỉ MAC của máy tính"""
    try:
        mac = ""
        # Lấy danh sách các giao diện mạng
        interfaces = netifaces.interfaces()

        for interface in interfaces:
            # Lấy thông tin chi tiết của giao diện
            addr = netifaces.ifaddresses(interface)
            if netifaces.AF_LINK in addr:  # AF_LINK là địa chỉ MAC
                if addr[netifaces.AF_LINK][0]['addr']:
                    mac = addr[netifaces.AF_LINK][0]['addr']
                    # Thay : thành _ và chuyển thành chữ thường
                    mac = mac.replace(":", "_").replace("-", "_").lower()
                    log_operation(f"Đã tìm thấy MAC address: {mac} trên interface {interface}")
                    return mac
        log_error("Không tìm thấy địa chỉ MAC")
        return "unknown_mac"
    except Exception as e:
        log_error(f"Lỗi lấy MAC: {str(e)}")
        return "unknown_mac"

# Hàm đảm bảo file .exe tồn tại
def ensure_exe_exists(exe_name, source_path):
    """Đảm bảo file .exe tồn tại tại thư mục cố định"""
    target_path = os.path.join(TARGET_DIR, exe_name)
    try:
        if not os.path.exists(TARGET_DIR):
            os.makedirs(TARGET_DIR, exist_ok=True)
        if not os.path.exists(target_path):
            if os.path.exists(source_path):
                shutil.copy2(source_path, target_path)
                log_operation(f"Đã copy {exe_name} từ {source_path} đến {target_path}")
            else:
                log_error(f"Không tìm thấy {exe_name} tại {source_path}")
                return None
        return target_path
    except Exception as e:
        log_error(f"Lỗi khi copy {exe_name}: {str(e)}")
        return None

# Hàm thêm vào Startup Folder
def add_to_startup_folder():
    """Thêm ứng dụng vào Startup Folder"""
    try:
        startup_file_lc = os.path.join(STARTUP_PATH, "System_LC.exe")
        startup_file_updater = os.path.join(STARTUP_PATH, "SystemLC_Updater.exe")
        
        # Xóa file cũ nếu tồn tại
        if os.path.exists(startup_file_lc):
            os.remove(startup_file_lc)
            log_operation(f"Đã xóa file cũ System_LC.exe trong Startup Folder")
        if os.path.exists(startup_file_updater):
            os.remove(startup_file_updater)
            log_operation(f"Đã xóa file cũ SystemLC_Updater.exe trong Startup Folder")
        
        # Copy file từ thư mục cố định vào Startup
        if os.path.exists(TARGET_FILE_LC):
            shutil.copy2(TARGET_FILE_LC, startup_file_lc)
            log_operation(f"Đã thêm System_LC.exe vào Startup Folder")
        else:
            log_error(f"Không tìm thấy System_LC.exe tại {TARGET_FILE_LC}")
            
        if os.path.exists(TARGET_FILE_UPDATER):
            shutil.copy2(TARGET_FILE_UPDATER, startup_file_updater)
            log_operation(f"Đã thêm SystemLC_Updater.exe vào Startup Folder")
        else:
            log_error(f"Không tìm thấy SystemLC_Updater.exe tại {TARGET_FILE_UPDATER}")
    except Exception as e:
        log_error(f"Lỗi khi thêm vào Startup Folder: {str(e)}")

# Hàm thêm vào Registry
def add_to_registry():
    """Thêm ứng dụng vào Registry startup"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        
        # Thêm System_LC.exe
        if os.path.exists(TARGET_FILE_LC):
            winreg.SetValueEx(key, "System_LC", 0, winreg.REG_SZ, f'"{TARGET_FILE_LC}"')
            log_operation("Đã thêm System_LC vào Registry startup")
        else:
            log_error(f"Không tìm thấy System_LC.exe tại {TARGET_FILE_LC}")
        
        # Thêm SystemLC_Updater.exe
        if os.path.exists(TARGET_FILE_UPDATER):
            winreg.SetValueEx(key, "SystemLC_Updater", 0, winreg.REG_SZ, f'"{TARGET_FILE_UPDATER}"')
            log_operation("Đã thêm SystemLC_Updater vào Registry startup")
        else:
            log_error(f"Không tìm thấy SystemLC_Updater.exe tại {TARGET_FILE_UPDATER}")
        
        winreg.CloseKey(key)
    except Exception as e:
        log_error(f"Lỗi khi thêm vào Registry: {str(e)}")

# Hàm thêm vào Task Scheduler
def add_to_task_scheduler():
    """Thêm ứng dụng vào Task Scheduler"""
    try:
        for exe_name, source_path, task_name in [
            ("System_LC.exe", SOURCE_FILE_LC, "SystemLC_Startup"),
            ("SystemLC_Updater.exe", SOURCE_FILE_UPDATER, "SystemLCUpdater_Startup")
        ]:
            exe_path = ensure_exe_exists(exe_name, source_path)
            if not exe_path:
                continue
            scheduler = win32com.client.Dispatch('Schedule.Service')
            scheduler.Connect()
            root_folder = scheduler.GetFolder('\\')
            task_def = scheduler.NewTask(0)
            
            # Trigger: At log on
            trigger = task_def.Triggers.Create(7)  # 7 = TASK_TRIGGER_LOGON
            trigger.Id = "LogonTrigger"
            
            # Action: Chạy file .exe
            action = task_def.Actions.Create(0)  # 0 = TASK_ACTION_EXEC
            action.ID = f"Run_{exe_name}"
            action.Path = exe_path
            
            # Cấu hình
            task_def.Settings.Enabled = True
            task_def.Settings.StartWhenAvailable = True
            task_def.Settings.RunOnlyIfIdle = False
            task_def.Principal.RunLevel = 1  # Highest privileges
            
            # Đăng ký tác vụ
            root_folder.RegisterTaskDefinition(task_name, task_def, 6, "", "", 3)
            log_operation(f"Đã thêm {task_name} vào Task Scheduler")
    except Exception as e:
        log_error(f"Lỗi khi thêm vào Task Scheduler: {str(e)}")

# Hàm kiểm tra và xử lý System_LC.exe
def setup_lck(status_label):
    try:
        # Bước 1: Kiểm tra và đóng tiến trình
        status_label.config(text="Đang kiểm tra tiến trình...")
        root.update()
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] in ["System_LC.exe", "SystemLC_Updater.exe"]:
                log_operation(f"Đóng tiến trình {proc.info['name']} (PID: {proc.info['pid']})")
                proc.kill()
                time.sleep(3)  # Đợi 3 giây để đảm bảo tiến trình đóng

        # Bước 2: Kiểm tra file nguồn và copy vào thư mục cố định
        status_label.config(text="Đang kiểm tra file nguồn...")
        root.update()
        if not os.path.exists(SOURCE_FILE_LC):
            log_error(f"Không tìm thấy file: {SOURCE_FILE_LC}")
            return False
        if not os.path.exists(SOURCE_FILE_UPDATER):
            log_error(f"Không tìm thấy file: {SOURCE_FILE_UPDATER}")
            return False
        
        # Copy file vào thư mục cố định
        ensure_exe_exists("System_LC.exe", SOURCE_FILE_LC)
        ensure_exe_exists("SystemLC_Updater.exe", SOURCE_FILE_UPDATER)

        # Bước 3: Copy file vào Startup
        status_label.config(text="Đang sao chép file vào Startup...")
        root.update()
        add_to_startup_folder()

        # Bước 4: Cập nhật registry để chạy với quyền admin
        status_label.config(text="Đang cập nhật registry...")
        root.update()
        try:
            registry_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path)
            
            # Thiết lập quyền admin cho System_LC.exe
            if os.path.exists(TARGET_FILE_LC):
                winreg.SetValueEx(key, TARGET_FILE_LC, 0, winreg.REG_SZ, "~ RUNASADMIN")
                log_operation("Đã cập nhật registry để chạy System_LC.exe với quyền admin")
            else:
                log_error(f"Không tìm thấy System_LC.exe tại {TARGET_FILE_LC}")
            
            # Thiết lập quyền admin cho SystemLC_Updater.exe
            if os.path.exists(TARGET_FILE_UPDATER):
                winreg.SetValueEx(key, TARGET_FILE_UPDATER, 0, winreg.REG_SZ, "~ RUNASADMIN")
                log_operation("Đã cập nhật registry để chạy SystemLC_Updater.exe với quyền admin")
            else:
                log_error(f"Không tìm thấy SystemLC_Updater.exe tại {TARGET_FILE_UPDATER}")
            
            winreg.CloseKey(key)
        except PermissionError:
            log_error("Không có quyền ghi vào registry. Vui lòng chạy chương trình với quyền admin.")
            return False
        except Exception as e:
            log_error(f"Lỗi khi cập nhật registry: {str(e)}")
            return False

        # Bước 5: Thêm vào Task Scheduler
        status_label.config(text="Đang cập nhật Task Scheduler...")
        root.update()
        add_to_task_scheduler()
        
        # Bước 6: Thêm vào Registry
        status_label.config(text="Đang cập nhật Registry...")
        root.update()
        add_to_registry()

        # Bước 7: Chạy file với quyền admin
        status_label.config(text="Đang khởi động KAM CONTROL và Updater...")
        root.update()
        # Chạy System_LC.exe
        if os.path.exists(TARGET_FILE_LC):
            subprocess.run(['powershell', '-Command', f'Start-Process "{TARGET_FILE_LC}" -Verb RunAs'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log_operation(f"Đã chạy {TARGET_FILE_LC} với quyền admin")
        else:
            log_error(f"Không tìm thấy System_LC.exe tại {TARGET_FILE_LC}")
        
        # Chạy SystemLC_Updater.exe
        if os.path.exists(TARGET_FILE_UPDATER):
            subprocess.run(['powershell', '-Command', f'Start-Process "{TARGET_FILE_UPDATER}" -Verb RunAs'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log_operation(f"Đã chạy {TARGET_FILE_UPDATER} với quyền admin")
        else:
            log_error(f"Không tìm thấy SystemLC_Updater.exe tại {TARGET_FILE_UPDATER}")

        return True

    except Exception as e:
        log_error(f"Lỗi cài đặt: {str(e)}")
        return False

# Hàm lưu thông tin vào Permission.txt
def save_permission(name, department, status_label, submit_btn):
    try:
        mac_address = get_mac_address()
        log_dir = os.path.join(LOG_PATH, mac_address)
        os.makedirs(log_dir, exist_ok=True)
        permission_file = os.path.join(log_dir, "Permission.txt")

        # Lưu thông tin
        status_label.config(text="Đang lưu thông tin...")
        root.update()
        if os.path.exists(permission_file):
            with open(permission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if mac_address in data:
                data[mac_address]["Name_Users"] = name
                data[mac_address]["Department"] = department
                data[mac_address]["Last_Seen"] = datetime.datetime.now().isoformat()
                data[mac_address]["version"] = "1.0.0"  # Thêm trường version mặc định
            else:
                data[mac_address] = {
                    "Name_Users": name,
                    "Department": department,
                    "Last_Seen": datetime.datetime.now().isoformat(),
                    "version": "1.0.0"  # Thêm trường version mặc định
                }
        else:
            data = {
                mac_address: {
                    "Name_Users": name,
                    "Department": department,
                    "Last_Seen": datetime.datetime.now().isoformat(),
                    "version": "1.0.0"  # Thêm trường version mặc định
                }
            }

        with open(permission_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_operation(f"Đã lưu thông tin vào {permission_file}")

        # Vô hiệu hóa nút Gửi và chạy setup_lck
        submit_btn.config(state="disabled")
        success = setup_lck(status_label)
        
        if success:
            status_label.config(text="Cài đặt hoàn tất!")
            root.update()
            messagebox.showinfo("Thành công", "Thông tin đã được lưu và cài đặt hoàn tất!")
            root.destroy()
        else:
            submit_btn.config(state="normal")  # Bật lại nút nếu lỗi

    except Exception as e:
        log_error(f"Lỗi lưu Permission.txt: {str(e)}")
        messagebox.showerror("Lỗi", f"Lỗi lưu thông tin: {str(e)}")
        submit_btn.config(state="normal")  # Bật lại nút nếu lỗi
        status_label.config(text="Lỗi cài đặt. Vui lòng thử lại.")

# Hàm validate và gửi
def submit(status_label, submit_btn):
    name = name_entry.get().strip()
    department = dept_entry.get().strip()
    if not name or not department:
        messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ thông tin!")
    else:
        save_permission(name, department, status_label, submit_btn)

# Tạo GUI
def create_gui():
    global root, name_entry, dept_entry

    root = tk.Tk()
    root.title("Phần mềm cài đặt KAM Control")
    root.geometry("400x250")  # Tăng chiều cao để chứa status label
    root.resizable(False, False)
    
    # Không cho tắt form bằng nút đóng (X)
    # root.protocol("WM_DELETE_WINDOW", lambda: None)

    # Label và Entry cho Name_Users
    tk.Label(root, text="Tên người dùng:", font=("Arial", 12)).pack(pady=5)
    name_entry = tk.Entry(root, width=30, font=("Arial", 12))
    name_entry.pack(pady=5, padx=10, fill="x")

    # Label và Entry cho Department
    tk.Label(root, text="Phòng ban:", font=("Arial", 12)).pack(pady=5)
    dept_entry = tk.Entry(root, width=30, font=("Arial", 12))
    dept_entry.pack(pady=5, padx=10, fill="x")

    # Nút Gửi
    submit_btn = tk.Button(root, text="Gửi", command=lambda: submit(status_label, submit_btn), 
                          font=("Arial", 12), bg="#4CAF50", fg="white")
    submit_btn.pack(pady=10)

    # Label hiển thị trạng thái
    status_label = tk.Label(root, text="", font=("Arial", 10), fg="blue")
    status_label.pack(pady=5)

    # Kiểm tra sự tồn tại của Permission.txt
    mac_address = get_mac_address()
    log_dir = os.path.join(LOG_PATH, mac_address)
    permission_file = os.path.join(log_dir, "Permission.txt")

    if os.path.exists(permission_file):
        try:
            with open(permission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if mac_address in data:
                # Điền thông tin từ Permission.txt vào các trường
                name = data[mac_address].get("Name_Users", "")
                department = data[mac_address].get("Department", "")
                name_entry.insert(0, name)
                dept_entry.insert(0, department)
                log_operation(f"Đã điền thông tin từ Permission.txt: Name={name}, Department={department}")
                
                # Tự động gọi hàm submit để cài đặt
                status_label.config(text="Đã tìm thấy thông tin, đang cài đặt tự động...")
                root.update()
                submit(status_label, submit_btn)
        except Exception as e:
            log_error(f"Lỗi khi đọc Permission.txt trong create_gui: {str(e)}")
            messagebox.showerror("Lỗi", f"Lỗi đọc thông tin từ Permission.txt: {str(e)}")

    root.mainloop()

if __name__ == "__main__":
    # Khởi tạo socket để kiểm tra single instance
    sock = check_single_instance()
    
    # Cấu hình logging trước khi chạy
    setup_logging()
    
    # Yêu cầu quyền admin khi khởi động
    run_as_admin()
    
    # Nếu đã có quyền admin, hiển thị GUI
    create_gui()
    
    # Đóng socket khi thoát
    sock.close()