#!/usr/bin/env python3
import json
import os
import sys
import time
import zipfile
import io
import re
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import hmac
import base64
import functools

# 加载环境变量
from dotenv import load_dotenv

# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 加载 .env 文件 (如果存在)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ================= 配置部分 =================

# Dropbox 分享链接 (dl=1 表示直接下载)
# 示例: https://www.dropbox.com/scl/fo/xxxxxxxx/xxxxxxxx?dl=1&rlkey=xxxxxxx
DROPBOX_URL = os.getenv("DROPBOX_SHARE_LINK")

# 本地存储路径配置
# 默认在脚本同级目录下创建 dropbox 和 data 文件夹
STORAGE_DIR = os.getenv("STORAGE_DIR", os.path.join(BASE_DIR, "downloads"))
DATA_DIR = os.path.join(BASE_DIR, "data")
SNAPSHOT_FILE = os.path.join(DATA_DIR, "snapshot.json")
LOG_FILE = os.path.join(BASE_DIR, "monitor.log")

# Lark (飞书) 配置
LARK_WEBHOOK_URL = os.getenv("LARK_WEBHOOK_URL")
LARK_SECRET = os.getenv("LARK_SECRET")
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_CHAT_ID = os.getenv("LARK_CHAT_ID")
# 用户指定的 Lark 云盘文件夹 Token (可选，用于上传文件到指定位置)
LARK_FOLDER_TOKEN = os.getenv("LARK_FOLDER_TOKEN") 

LARK_BASE_URL = "https://open.larksuite.com"

# ===========================================

def log(message):
    """记录日志到文件和标准输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except: pass

def retry(max_attempts=3, delay=5):
    """简单的重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
                    attempts += 1
                    log(f"网络异常 ({e}), 正在尝试第 {attempts}/{max_attempts} 次重试...")
                    if attempts == max_attempts:
                        log(f"重试 {max_attempts} 次后依然失败，停止本次操作。")
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def clean_filename(filename):
    """
    文件名标准化:
    1. 英文之间的空格用 - 替代
    2. 去除首尾空格
    3. 转为小写
    """
    name, ext = os.path.splitext(filename)
    if not name: return filename
    name = name.lower()
    name = re.sub(r'\s*-\s*', '-', name)
    name = re.sub(r'\s+', '-', name)
    return f"{name}{ext}"

class DropboxMonitor:
    def __init__(self, url):
        self.url = url

    @retry(max_attempts=3, delay=10)
    def process_updates(self):
        """下载 zip，保存文件并返回新文件列表"""
        if not self.url:
            log("错误: 未配置 DROPBOX_SHARE_LINK 环境变量")
            return []

        log("正在检查 Dropbox 更新...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(self.url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as response:
            zip_content = response.read()
            
        os.makedirs(STORAGE_DIR, exist_ok=True)
        
        processed_files = []
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            for member in z.infolist():
                if member.is_dir(): continue
                original_name = os.path.basename(member.filename)
                if not original_name: continue
                # 忽略隐藏文件
                if original_name.startswith('.'): continue
                
                cleaned_name = clean_filename(original_name)
                target_path = os.path.join(STORAGE_DIR, cleaned_name)
                
                with z.open(member) as f:
                    file_data = f.read()
                    
                processed_files.append({
                    "original": original_name,
                    "cleaned": cleaned_name,
                    "data": file_data,
                    "path": target_path
                })
        return processed_files

class LarkNotifier:
    def __init__(self, webhook_url=None, secret=None, app_id=None, app_secret=None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.app_id = app_id
        self.app_secret = app_secret

    @retry(max_attempts=3, delay=5)
    def _get_tenant_token(self):
        if not self.app_id or not self.app_secret: return None
        url = f"{LARK_BASE_URL}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode())
            return res.get("tenant_access_token")

    @retry(max_attempts=3, delay=5)
    def upload_to_drive(self, file_path, file_name):
        """上传文件到 Lark Drive"""
        token = self._get_tenant_token()
        if not token: return None
        
        file_size = os.path.getsize(file_path)
        url = f"{LARK_BASE_URL}/open-apis/drive/v1/files/upload_all"
        boundary = '----LarkDriveBoundary' + str(int(time.time()))
        
        with open(file_path, 'rb') as f:
            file_content = f.read()

        parts = []
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="file_name"\r\n\r\n'.encode())
        parts.append(f'{file_name}\r\n'.encode())
        
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="parent_type"\r\n\r\n'.encode())
        parts.append(b'explorer\r\n')
        
        # 如果配置了文件夹 Token，则上传到指定文件夹，否则上传到根目录
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="parent_token"\r\n\r\n'.encode())
        if LARK_FOLDER_TOKEN:
            parts.append(f'{LARK_FOLDER_TOKEN}\r\n'.encode())
        else:
            parts.append(b'\r\n')
        
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="size"\r\n\r\n'.encode())
        parts.append(f'{file_size}\r\n'.encode())
        
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode())
        # 简单判定 PDF，可根据需要扩展
        content_type = 'application/pdf' if file_name.endswith('.pdf') else 'application/octet-stream'
        parts.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
        parts.append(file_content)
        parts.append(f'\r\n--{boundary}--\r\n'.encode())
        
        data = b''.join(parts)
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(data))
        }
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                res = json.loads(response.read().decode())
                if res.get("code") == 0:
                    file_token = res.get("data", {}).get("file_token")
                    # 构造文件访问链接
                    file_url = f"https://www.larksuite.com/file/{file_token}" # 通用域名
                    return {"token": file_token, "url": file_url}
                log(f"Drive 上传失败: {res}")
                return None
        except Exception as e:
            log(f"Drive 上传异常: {e}")
            return None

    @retry(max_attempts=3, delay=5)
    def send_webhook_notification(self, title, message, color="blue"):
        if not self.webhook_url: return
        timestamp = str(int(time.time()))
        data = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": message}}]
            }
        }
        if self.secret:
            string_to_sign = f"{timestamp}\n{self.secret}"
            hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
            data["timestamp"], data["sign"] = timestamp, base64.b64encode(hmac_code).decode("utf-8")
        
        try:
            req = urllib.request.Request(self.webhook_url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status not in [200, 201]: raise urllib.error.URLError(f"HTTP Status {response.status}")
            log("通知已发送。")
        except Exception as e:
            log(f"发送通知失败: {e}")

def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_snapshot(data):
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, 'w') as f: json.dump(data, f, indent=4)

def main():
    if not DROPBOX_URL:
        print("错误: 请先在 .env 文件中配置 DROPBOX_SHARE_LINK")
        return

    monitor = DropboxMonitor(DROPBOX_URL)
    notifier = LarkNotifier(LARK_WEBHOOK_URL, LARK_SECRET, LARK_APP_ID, LARK_APP_SECRET)
    
    # 尝试获取更新
    try:
        processed_items = monitor.process_updates()
    except Exception:
        log("无法获取文件列表。")
        return

    if not processed_items:
        log("未找到任何文件。")
        return

    old_snapshot = load_snapshot()
    new_items = []
    
    # 对比快照，下载新文件
    for item in processed_items:
        if item['cleaned'] not in old_snapshot or not os.path.exists(item['path']):
            try:
                with open(item['path'], 'wb') as f: f.write(item['data'])
                log(f"已下载: {item['cleaned']}")
                new_items.append(item)
            except Exception as e: log(f"保存失败 {item['cleaned']}: {e}")

    # 处理通知
    if new_items:
        # 按文件名排序，取最新
        new_items.sort(key=lambda x: x['cleaned'])
        latest_item = new_items[-1]
        
        log(f"发现新文件，准备推送: {latest_item['cleaned']}")
        
        # 上传到 Lark Drive
        drive_result = None
        if LARK_APP_ID and LARK_APP_SECRET:
            log(f"正在上传到 Lark Drive...")
            drive_result = notifier.upload_to_drive(latest_item['path'], latest_item['cleaned'])
            
        # 构造消息
        msg_header = "🔔 Dropbox 文件更新"
        msg_body = f"**最新文件：**\n{latest_item['cleaned']}\n\n"
        
        if drive_result and drive_result.get('url'):
            msg_body += f"[📂 点击查看云文档]({drive_result['url']})\n"
        else:
            # 如果没上传或者上传失败，给原始链接（去掉 dl=1）
            preview_url = DROPBOX_URL.replace("dl=1", "dl=0")
            msg_body += f"[点击前往 Dropbox 查看]({preview_url})"
            
        notifier.send_webhook_notification("监控提醒-🚨", f"{msg_header}\n\n{msg_body}", "orange")

        # 更新快照
        save_snapshot(sorted(list(set(old_snapshot) | {i['cleaned'] for i in processed_items})))
    else:
        log("无新文件。")
        # 可选：发送心跳 (取消注释以下行)
        # notifier.send_webhook_notification("监控心跳-✖️", "暂无更新", "grey")

if __name__ == "__main__":
    main()
