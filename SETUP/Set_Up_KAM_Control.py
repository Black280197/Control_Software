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

# Đường dẫn mạng và startup
NETWORK_PATH = r"\\10.0.0.125\\9.2. dùng chung\\3. ERP-KPI-TRIEN KHAI\\ERP_Manager\\Check New App"
SOURCE_FILE_LC = os.path.join(NETWORK_PATH, "System_LC.exe")  # File System_LC.exe
SOURCE_FILE_UPDATER = os.path.join(NETWORK_PATH, "SystemLC_Updater.exe")  # File SystemLC_Updater.exe
STARTUP_PATH = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
TARGET_FILE_LC = os.path.join(STARTUP_PATH, "System_LC.exe")  # Đích cho System_LC.exe
TARGET_FILE_UPDATER = os.path.join(STARTUP_PATH, "SystemLC_Updater.exe")  # Đích cho SystemLC_Updater.exe
LOG_PATH = os.path.join(NETWORK_PATH, "LOG")

# Thêm biến toàn cục cho logging
LOGGING_DIR = None  # Thư mục loggingOfApp
ERROR_LOG = None    # File error.log
OPERATION_LOG = None  # File operation.log

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

# Đường dẫn mạng và startup
NETWORK_PATH = r"\\10.0.0.125\\9.2. dùng chung\\3. ERP-KPI-TRIEN KHAI\\ERP_Manager\\Check New App"
SOURCE_FILE_LC = os.path.join(NETWORK_PATH, "System_LC.exe")  # File System_LC.exe
SOURCE_FILE_UPDATER = os.path.join(NETWORK_PATH, "SystemLC_Updater.exe")  # File SystemLC_Updater.exe
STARTUP_PATH = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
TARGET_FILE_LC = os.path.join(STARTUP_PATH, "System_LC.exe")  # Đích cho System_LC.exe
TARGET_FILE_UPDATER = os.path.join(STARTUP_PATH, "SystemLC_Updater.exe")  # Đích cho SystemLC_Updater.exe
LOG_PATH = os.path.join(NETWORK_PATH, "LOG")

# Hàm kiểm tra quyền admin
def is_admin():
    try:
        return os.getuid() == 0  # Linux
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # Windows

# Hàm yêu cầu quyền admin
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

        # Bước 2: Kiểm tra file nguồn
        status_label.config(text="Đang kiểm tra file nguồn...")
        root.update()
        if not os.path.exists(SOURCE_FILE_LC):
            log_error(f"Không tìm thấy file: {SOURCE_FILE_LC}")
            return False
        if not os.path.exists(SOURCE_FILE_UPDATER):
            log_error(f"Không tìm thấy file: {SOURCE_FILE_UPDATER}")
            return False

        # Bước 3: Copy file vào Startup
        status_label.config(text="Đang sao chép file...")
        root.update()
        # Xử lý System_LC.exe
        if os.path.exists(TARGET_FILE_LC):
            subprocess.run(['cmd', '/c', 'del', '/f', '/q', TARGET_FILE_LC], shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        shutil.copy2(SOURCE_FILE_LC, TARGET_FILE_LC)
        log_operation(f"Đã copy file từ {SOURCE_FILE_LC} đến {TARGET_FILE_LC}")
        
        # Xử lý SystemLC_Updater.exe
        if os.path.exists(TARGET_FILE_UPDATER):
            subprocess.run(['cmd', '/c', 'del', '/f', '/q', TARGET_FILE_UPDATER], shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        shutil.copy2(SOURCE_FILE_UPDATER, TARGET_FILE_UPDATER)
        log_operation(f"Đã copy file từ {SOURCE_FILE_UPDATER} đến {TARGET_FILE_UPDATER}")

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
            winreg.SetValueEx(key, TARGET_FILE_LC, 0, winreg.REG_SZ, "~ RUNASADMIN")
            log_operation("Đã cập nhật registry để chạy System_LC.exe với quyền admin")
            
            # Thiết lập quyền admin cho SystemLC_Updater.exe
            winreg.SetValueEx(key, TARGET_FILE_UPDATER, 0, winreg.REG_SZ, "~ RUNASADMIN")
            log_operation("Đã cập nhật registry để chạy SystemLC_Updater.exe với quyền admin")
            
            winreg.CloseKey(key)
        except PermissionError:
            log_error("Không có quyền ghi vào registry. Vui lòng chạy chương trình với quyền admin.")
            return False
        except Exception as e:
            log_error(f"Lỗi khi cập nhật registry: {str(e)}")
            return False

        # Bước 5: Chạy file với quyền admin
        status_label.config(text="Đang khởi động KAM CONTROL và Updater...")
        root.update()
        # Chạy System_LC.exe
        subprocess.run(['powershell', '-Command', f'Start-Process "{TARGET_FILE_LC}" -Verb RunAs'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        log_operation(f"Đã chạy {TARGET_FILE_LC} với quyền admin")
        
        # Chạy SystemLC_Updater.exe
        subprocess.run(['powershell', '-Command', f'Start-Process "{TARGET_FILE_UPDATER}" -Verb RunAs'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        log_operation(f"Đã chạy {TARGET_FILE_UPDATER} với quyền admin")

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
    # Cấu hình logging trước khi chạy
    setup_logging()
    
    # Yêu cầu quyền admin khi khởi động
    run_as_admin()
    
    # Nếu đã có quyền admin, hiển thị GUI
    create_gui()