import os
import json
import psutil
import netifaces
import subprocess
import shutil
import time
import logging
import sys
import winreg
import datetime

# Đường dẫn mạng và các file
NETWORK_PATH = r"\\10.0.0.125\\9.2. dùng chung\\3. ERP-KPI-TRIEN KHAI\\ERP_Manager\\Check New App"
SOURCE_FILE = os.path.join(NETWORK_PATH, "System_LC.exe")
STARTUP_PATH = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
TARGET_FILE = os.path.join(STARTUP_PATH, "System_LC.exe")
LOG_PATH = os.path.join(NETWORK_PATH, "LOG")
VERSION_FILE = os.path.join(NETWORK_PATH, "NewestVersion.txt")

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
    LOGGING_DIR = os.path.join(log_dir, "loggingOfUpdater")
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

# Hàm đọc phiên bản hiện tại từ Permission.txt
def get_current_version():
    try:
        mac_address = get_mac_address()
        permission_file = os.path.join(LOG_PATH, mac_address, "Permission.txt")
        
        if not os.path.exists(permission_file):
            log_error(f"Không tìm thấy file Permission.txt tại {permission_file}")
            return None

        with open(permission_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if mac_address not in data:
            log_error(f"Không tìm thấy thông tin MAC {mac_address} trong Permission.txt")
            return None
        
        version = data[mac_address].get("version", "0.0.0")  # Mặc định là 0.0.0 nếu không có trường version
        log_operation(f"Phiên bản hiện tại từ Permission.txt: {version}")
        return version

    except Exception as e:
        log_error(f"Lỗi khi đọc phiên bản từ Permission.txt: {str(e)}")
        return None

# Hàm đọc phiên bản mới nhất từ NewestVersion.txt
def get_latest_version():
    try:
        if not os.path.exists(VERSION_FILE):
            log_error(f"Không tìm thấy file NewestVersion.txt tại {VERSION_FILE}")
            return None

        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            latest_version = f.readline().strip()
        
        log_operation(f"Phiên bản mới nhất từ NewestVersion.txt: {latest_version}")
        return latest_version

    except Exception as e:
        log_error(f"Lỗi khi đọc NewestVersion.txt: {str(e)}")
        return None

# Hàm so sánh phiên bản
def compare_versions(current, latest):
    """So sánh hai phiên bản (định dạng x.y.z)"""
    try:
        current_parts = list(map(int, current.split(".")))
        latest_parts = list(map(int, latest.split(".")))
        
        for i in range(len(current_parts)):
            if current_parts[i] < latest_parts[i]:
                return -1
            elif current_parts[i] > latest_parts[i]:
                return 1
        return 0
    except Exception as e:
        log_error(f"Lỗi khi so sánh phiên bản: {str(e)}")
        return -1  # Giả định phiên bản hiện tại lỗi thời nếu có lỗi

# Hàm cập nhật System_LC.exe (tương tự setup_lck)
def update_system_lce():
    try:
        # Bước 1: Kiểm tra và đóng tiến trình
        log_operation("Đang kiểm tra và đóng tiến trình System_LC.exe...")
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == "System_LC.exe":
                log_operation(f"Đóng tiến trình System_LC.exe (PID: {proc.info['pid']})")
                proc.kill()
                time.sleep(3)  # Đợi 3 giây để đảm bảo tiến trình đóng

        # Bước 2: Kiểm tra file nguồn
        log_operation("Đang kiểm tra file nguồn...")
        if not os.path.exists(SOURCE_FILE):
            log_error(f"Không tìm thấy file: {SOURCE_FILE}")
            return False

        # Bước 3: Copy file vào Startup
        log_operation("Đang sao chép file vào Startup...")
        if os.path.exists(TARGET_FILE):
            subprocess.run(['cmd', '/c', 'del', '/f', '/q', TARGET_FILE], shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        shutil.copy2(SOURCE_FILE, TARGET_FILE)
        log_operation(f"Đã copy file từ {SOURCE_FILE} đến {TARGET_FILE}")

        # Bước 4: Cập nhật registry để chạy với quyền admin
        log_operation("Đang cập nhật registry...")
        try:
            registry_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, winreg.KEY_SET_VALUE)
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path)
            
            winreg.SetValueEx(key, TARGET_FILE, 0, winreg.REG_SZ, "~ RUNASADMIN")
            winreg.CloseKey(key)
            log_operation("Đã cập nhật registry để chạy TARGET_FILE với quyền admin")
        except PermissionError:
            log_error("Không có quyền ghi vào registry. Vui lòng chạy chương trình với quyền admin.")
            return False
        except Exception as e:
            log_error(f"Lỗi khi cập nhật registry: {str(e)}")
            return False

        # Bước 5: Chạy file với quyền admin
        log_operation("Đang khởi động System_LC.exe với quyền admin...")
        subprocess.run(['powershell', '-Command', f'Start-Process "{TARGET_FILE}" -Verb RunAs'], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        log_operation(f"Đã chạy {TARGET_FILE} với quyền admin")

        # Cập nhật phiên bản trong Permission.txt
        mac_address = get_mac_address()
        permission_file = os.path.join(LOG_PATH, mac_address, "Permission.txt")
        if os.path.exists(permission_file):
            with open(permission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if mac_address in data:
                data[mac_address]["version"] = get_latest_version()
                data[mac_address]["Last_Seen"] = datetime.datetime.now().isoformat()
                with open(permission_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log_operation(f"Đã cập nhật phiên bản trong Permission.txt lên {data[mac_address]['version']}")

        return True

    except Exception as e:
        log_error(f"Lỗi khi cập nhật System_LC.exe: {str(e)}")
        return False

# Hàm kiểm tra và cập nhật
def check_and_update():
    current_version = get_current_version()
    latest_version = get_latest_version()

    if current_version is None or latest_version is None:
        log_error("Không thể kiểm tra phiên bản do lỗi đọc file")
        return False

    if compare_versions(current_version, latest_version) < 0:
        log_operation(f"Phiên bản hiện tại ({current_version}) đã lỗi thời. Cập nhật lên phiên bản {latest_version}...")
        success = update_system_lce()
        if success:
            log_operation(f"Cập nhật thành công lên phiên bản {latest_version}")
        else:
            log_error("Cập nhật thất bại")
        return success
    else:
        log_operation(f"Ứng dụng đang chạy phiên bản mới nhất: {current_version}")
        return False

# Vòng lặp chính
if __name__ == "__main__":
    # Cấu hình logging trước khi chạy
    setup_logging()
    
    # Yêu cầu quyền admin khi khởi động
    run_as_admin()

    # Vòng lặp kiểm tra cập nhật mỗi 30 phút
    while True:
        try:
            log_operation(f"Bắt đầu kiểm tra cập nhật vào {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            check_and_update()
            log_operation("Hoàn tất kiểm tra cập nhật. Đợi 30 phút để kiểm tra lại...")
            time.sleep(30 * 60)  # Chờ 30 phút (30 * 60 giây)
        except Exception as e:
            log_error(f"Lỗi trong vòng lặp cập nhật: {str(e)}")
            time.sleep(5 * 60)  # Nếu lỗi, chờ 5 phút rồi thử lại