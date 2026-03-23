import asyncio
import aiohttp
import aiohttp.client_exceptions
import time
import os
import sys
import hashlib
import random
import gc
import psutil
import signal
from collections import defaultdict
from datetime import datetime
import tracemalloc

tracemalloc.start()

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    RAINBOW = [RED, YELLOW, GREEN, CYAN, BLUE, PURPLE]

sent_messages = 0
failed_messages = 0
rate_limit_hits = 0
proxies = []
token_delays = {}
token_rate_limit_times = defaultdict(float)
semaphore = None
stop_event = asyncio.Event()

active_tokens = []
invalid_tokens = set()
token_last_used = {}
token_fail_count = {}
token_success_count = {}
token_lock = asyncio.Lock()

last_cleanup_time = time.time()
CLEANUP_INTERVAL = 300
MAX_MEMORY_PERCENT = 80

online_tasks = []

request_tracker = {
    "requests": [],
    "last_reset": time.time(),
    "consecutive_failures": 0
}

MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "Discord-Android/231.15 - (https://discord.app)",
    "Discord-iOS/231.15 - (https://discord.app)",
]

token_user_agent = {}

def get_mobile_user_agent(token):
    if token not in token_user_agent:
        token_user_agent[token] = random.choice(MOBILE_USER_AGENTS)
    return token_user_agent[token]

def generate_request_fingerprint():
    timestamp = str(int(time.time() * 1000))
    random_id = str(random.randint(100000, 999999))
    return hashlib.md5(f"{timestamp}{random_id}".encode()).hexdigest()

def get_smart_headers(token):
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": get_mobile_user_agent(token),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "X-Super-Properties": generate_request_fingerprint(),
        "X-Client-Version": "231.15",
        "X-Client-Type": "mobile"
    }

def color_rainbow(text):
    result = ""
    colors = Colors.RAINBOW
    for i, char in enumerate(text):
        color = colors[i % len(colors)]
        result += f"{color}{char}"
    result += Colors.RESET
    return result

def color_gradient(text, start_color, end_color):
    return f"{start_color}{text}{Colors.RESET}"

def log_info(msg):
    print(color_rainbow(f"[INFO] {msg}"))

def log_success(msg):
    print(f"{Colors.GREEN}[SUCCESS] {msg}{Colors.RESET}")

def log_warning(msg):
    print(f"{Colors.YELLOW}[WARNING] {msg}{Colors.RESET}")

def log_error(msg):
    print(f"{Colors.RED}[ERROR] {msg}{Colors.RESET}")

def log_input(msg):
    print(color_rainbow(f"[INPUT] {msg}"), end="")
    return input()

def log_memory():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    cpu_percent = process.cpu_percent()
    system_memory = psutil.virtual_memory()
    print(f"{Colors.PURPLE}[MEMORY] RAM: {memory_mb:.2f} MB | CPU: {cpu_percent:.1f}% | System: {system_memory.percent}%{Colors.RESET}")
    return memory_mb

def read_proxies(file_name):
    if not os.path.exists(file_name):
        return []
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            proxy_list = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '://' in line:
                        proxy_list.append(line)
                    else:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            if len(parts) == 2:
                                proxy_url = f"http://{parts[0]}:{parts[1]}"
                                proxy_list.append(proxy_url)
                            elif len(parts) == 4:
                                proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                                proxy_list.append(proxy_url)
            return proxy_list
    except:
        return []

def read_tokens(file_name):
    if not os.path.exists(file_name):
        return []
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

async def get_channel_and_server_info(session, token, channel_id):
    headers = get_smart_headers(token)
    try:
        async with session.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers, timeout=5) as response:
            if response.status == 200:
                channel_data = await response.json()
                channel_name = channel_data.get("name", "Unknown")
                guild_id = channel_data.get("guild_id")
                if guild_id:
                    async with session.get(f"https://discord.com/api/v9/guilds/{guild_id}", headers=headers, timeout=5) as guild_response:
                        if guild_response.status == 200:
                            guild_data = await guild_response.json()
                            server_name = guild_data.get("name", "Unknown")
                            return channel_name, server_name
        return "Unknown", "Unknown"
    except:
        return "Unknown", "Unknown"

def update_request_tracker(success=True):
    global request_tracker
    current_time = time.time()
    if current_time - request_tracker["last_reset"] >= 60:
        request_tracker["requests"] = []
        request_tracker["last_reset"] = current_time
        request_tracker["consecutive_failures"] = 0
    request_tracker["requests"].append(current_time)
    request_tracker["consecutive_failures"] = 0 if success else request_tracker["consecutive_failures"] + 1

def calculate_adaptive_delay(base_delay, consecutive_success, consecutive_failures):
    if consecutive_failures > 8:
        return min(base_delay * 1.5, 2.0)
    elif consecutive_success > 5:
        return max(base_delay * 0.1, 0.005)
    else:
        return base_delay + random.uniform(-0.02, 0.02)

def handle_rate_limit(token, retry_after=None):
    current_time = time.time()
    if retry_after:
        wait_time = float(retry_after) * 0.1
    else:
        base_wait = 0.5
        rate_limit_count = token_rate_limit_times.get(token, 0)
        wait_time = base_wait * (rate_limit_count + 1) * 0.5
    token_rate_limit_times[token] = current_time + wait_time
    return wait_time

async def cleanup_invalid_tokens():
    global active_tokens, invalid_tokens, last_cleanup_time
    async with token_lock:
        before_count = len(active_tokens)
        active_tokens = [t for t in active_tokens if t not in invalid_tokens]
        for token in invalid_tokens:
            if token in token_fail_count:
                del token_fail_count[token]
            if token in token_success_count:
                del token_success_count[token]
            if token in token_last_used:
                del token_last_used[token]
            if token in token_rate_limit_times:
                del token_rate_limit_times[token]
            if token in token_user_agent:
                del token_user_agent[token]
        removed = before_count - len(active_tokens)
        gc.collect()
        log_memory()
        if removed > 0:
            log_success(f"CLEANUP: Xoa {removed} token die | Con {len(active_tokens)} token")
        last_cleanup_time = time.time()
        return removed

async def periodic_cleanup():
    global last_cleanup_time
    while not stop_event.is_set():
        try:
            await asyncio.sleep(60)
            current_time = time.time()
            time_since_cleanup = current_time - last_cleanup_time
            process = psutil.Process(os.getpid())
            memory_percent = process.memory_percent()
            system_memory = psutil.virtual_memory()
            should_cleanup = (time_since_cleanup >= CLEANUP_INTERVAL or memory_percent > MAX_MEMORY_PERCENT or system_memory.percent > 90)
            if should_cleanup:
                await cleanup_invalid_tokens()
        except Exception as e:
            log_error(f"Loi cleanup: {e}")

async def send_typing(session, channel_id, headers):
    try:
        async with session.post(f"https://discord.com/api/v9/channels/{channel_id}/typing", headers=headers, timeout=2) as response:
            return response.status == 204
    except:
        return False

async def keep_online_task(token, stop_event):
    headers = get_smart_headers(token)
    fail_count = 0
    while not stop_event.is_set():
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.patch("https://discord.com/api/v9/users/@me/settings", headers=headers, json={'status': 'online'}, timeout=5) as response:
                    if response.status == 200:
                        print(f"{Colors.GREEN}[ONLINE] {token[:6]}...{token[-6:]}{Colors.RESET}")
                        fail_count = 0
                    elif response.status == 429:
                        retry_after = response.headers.get('Retry-After', 60)
                        wait_time = int(retry_after) + 10
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        fail_count += 1
                        if fail_count >= 5:
                            await asyncio.sleep(300)
                            fail_count = 0
        except:
            fail_count += 1
        for _ in range(60):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)

async def log_message(channel_name, server_name, content, token, status="Success", proxy=None, typing_time=0):
    global sent_messages, failed_messages
    short_token = f"{token[:6]}...{token[-6:]}"
    content_preview = content[:30] + ("..." if len(content) > 30 else "")
    gio = datetime.now().strftime("%H|%M|%S")
    if status == "Success":
        sent_messages += 1
        if sent_messages % 100 == 0:
            log_memory()
        print(color_gradient(f"[{gio}] >> {short_token} | {channel_name} | {content_preview} | Send: {sent_messages}", Colors.GREEN, Colors.CYAN))
    else:
        failed_messages += 1

async def spam_task(semaphore, token, channel_id, channel_info, contents, base_delay, proxy_list, task_id, typing_delay):
    global active_tokens, invalid_tokens, stop_event
    channel_name = channel_info.get("name", "Unknown")
    content_index = task_id % len(contents)
    consecutive_success = 0
    consecutive_failures = 0
    token_delay = token_delays.get(token, base_delay)
    proxy_index = 0
    
    while not stop_event.is_set():
        try:
            if token in invalid_tokens:
                break
            
            async with semaphore:
                current_time = time.time()
                if current_time < token_rate_limit_times.get(token, 0):
                    wait_time = token_rate_limit_times[token] - current_time
                    await asyncio.sleep(wait_time * 0.5)
                    continue
                
                proxy = None
                if proxy_list:
                    proxy = proxy_list[proxy_index % len(proxy_list)]
                    proxy_index += 1
                
                headers = get_smart_headers(token)
                typing_start = time.time()
                connector = aiohttp.TCPConnector(ssl=False, limit=0, ttl_dns_cache=300, force_close=True)
                
                try:
                    async with aiohttp.ClientSession(connector=connector) as session:
                        typing_task = asyncio.create_task(send_typing(session, channel_id, headers))
                        await asyncio.sleep(typing_delay)
                        await typing_task
                        payload = {"content": contents[content_index]}
                        content_index = (content_index + 1) % len(contents)
                        
                        try:
                            async with session.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", headers=headers, json=payload, proxy=proxy, timeout=aiohttp.ClientTimeout(total=3)) as response:
                                typing_time = time.time() - typing_start
                                if response.status == 404:
                                    async with token_lock:
                                        if token not in invalid_tokens:
                                            invalid_tokens.add(token)
                                            log_error(f"TOKEN 404: {token[:6]}...{token[-6:]}")
                                            if len(invalid_tokens) % 5 == 0:
                                                asyncio.create_task(cleanup_invalid_tokens())
                                    break
                                elif response.status == 429:
                                    global rate_limit_hits
                                    rate_limit_hits += 1
                                    consecutive_failures += 1
                                    consecutive_success = 0
                                    token_fail_count[token] = token_fail_count.get(token, 0) + 1
                                    retry_after = response.headers.get('Retry-After')
                                    handle_rate_limit(token, retry_after)
                                    update_request_tracker(False)
                                    await asyncio.sleep(0.01)
                                elif response.status == 200:
                                    await log_message(channel_name, "", contents[content_index], token, "Success", proxy, typing_time)
                                    consecutive_success += 1
                                    consecutive_failures = 0
                                    token_success_count[token] = token_success_count.get(token, 0) + 1
                                    token_fail_count[token] = 0
                                    update_request_tracker(True)
                                    adaptive_delay = calculate_adaptive_delay(token_delay, consecutive_success, consecutive_failures)
                                    await asyncio.sleep(adaptive_delay)
                                else:
                                    consecutive_failures += 1
                                    consecutive_success = 0
                                    token_fail_count[token] = token_fail_count.get(token, 0) + 1
                                    update_request_tracker(False)
                                    if token_fail_count.get(token, 0) >= 10:
                                        async with token_lock:
                                            if token not in invalid_tokens:
                                                invalid_tokens.add(token)
                                                log_warning(f"TOKEN FAIL 10: {token[:6]}...{token[-6:]}")
                                        break
                                    await asyncio.sleep(0.1)
                        except:
                            consecutive_failures += 1
                            token_fail_count[token] = token_fail_count.get(token, 0) + 1
                            if proxy_list:
                                proxy_index += 1
                            await asyncio.sleep(0.1)
                except:
                    await asyncio.sleep(0.1)
                finally:
                    await connector.close()
        except asyncio.CancelledError:
            break
        except:
            await asyncio.sleep(0.1)

async def main_async():
    global semaphore, token_delays, stop_event, active_tokens, online_tasks
    
    print(color_gradient("\n" + "="*60, Colors.CYAN, Colors.BLUE))
    log_info("DISCORD SPAM TOOL")
    print(color_gradient("="*60, Colors.CYAN, Colors.BLUE))
    
    # Nhap token truc tiep
    tokens = []
    print(color_rainbow("[INPUT] Nhap token (nhap 'done' de dung):"))
    while True:
        token_input = log_input("Token: ").strip()
        if token_input.lower() == "done":
            if not tokens:
                log_error("Can it nhat 1 token!")
                continue
            break
        if token_input:
            tokens.append(token_input)
            log_success(f"Them token: {token_input[:6]}...{token_input[-6:]}")
    
    active_tokens = tokens.copy()
    log_success(f"Tong so token: {len(tokens)}")
    
    # Khoi dong keep online
    for token in active_tokens:
        online_task = asyncio.create_task(keep_online_task(token, stop_event))
        online_tasks.append(online_task)
    log_success(f"Da khoi dong {len(online_tasks)} task keep online")
    
    # Nhap channel id
    channel_ids = []
    channel_info = {}
    print(color_rainbow("[INPUT] Nhap channel ID (nhap 'done' de dung):"))
    while True:
        channel_id = log_input("Channel ID: ").strip()
        if channel_id.lower() == "done":
            if not channel_ids:
                log_error("Can it nhat 1 channel!")
                continue
            break
        if channel_id.isdigit():
            channel_ids.append(channel_id)
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                channel_name, server_name = await get_channel_and_server_info(session, tokens[0], channel_id)
                channel_info[channel_id] = {"name": channel_name, "server": server_name}
            await connector.close()
            log_success(f"Them channel: {channel_name}")
        else:
            log_warning("ID channel phai la so!")
    
    # Nhap tasks
    tasks_per_token = log_input("Tasks/token [10]: ").strip() or "10"
    try:
        tasks_per_token = int(tasks_per_token)
    except:
        tasks_per_token = 10
    log_success(f"Tasks: {tasks_per_token}")
    
    # Nhap delay
    delay_input = log_input("Delay (giay) [5]: ").strip() or "5"
    try:
        base_delay = float(delay_input)
        if base_delay < 0:
            base_delay = 5
    except:
        base_delay = 5
    log_success(f"Delay: {base_delay}s")
    
    # Nhap typing delay
    typing_delay_input = log_input("Typing delay (giay) [2]: ").strip() or "2"
    try:
        typing_delay = float(typing_delay_input)
        if typing_delay < 0.5:
            typing_delay = 0.5
        elif typing_delay > 5:
            typing_delay = 5
    except:
        typing_delay = 2.0
    log_success(f"Typing delay: {typing_delay}s")
    
    # Nhap file noi dung
    content_files = []
    print(color_rainbow("[INPUT] Nhap file noi dung (nhap 'done' de dung):"))
    while True:
        file_name = log_input("File: ").strip()
        if file_name.lower() == "done":
            if not content_files:
                log_error("Can it nhat 1 file noi dung!")
                continue
            break
        if os.path.exists(file_name):
            content_files.append(file_name)
            log_success(f"Them file: {file_name}")
        else:
            log_warning(f"File {file_name} khong ton tai!")
    
    contents = []
    for f in content_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if content:
                    contents.append(content)
        except:
            log_warning(f"Loi doc file {f}")
    
    if not contents:
        log_error("Khong co noi dung hop le!")
        return
    
    # Nhap proxy
    proxy_file = log_input("File proxy (nhap 'skip' de bo qua): ").strip()
    proxy_list = []
    if proxy_file.lower() != "skip":
        if os.path.exists(proxy_file):
            proxy_list = read_proxies(proxy_file)
            if proxy_list:
                log_success(f"Dung {len(proxy_list)} proxy")
    
    # Setup delay tung token
    log_info("Setup delay tung token:")
    for i, token in enumerate(tokens, 1):
        token_delay_input = log_input(f"Delay token {i} [{base_delay}s]: ").strip() or str(base_delay)
        try:
            token_delay = float(token_delay_input)
            token_delays[token] = token_delay if token_delay >= 0 else base_delay
        except:
            token_delays[token] = base_delay
    
    max_concurrent = tasks_per_token * len(active_tokens) * len(channel_ids) * 2
    semaphore = asyncio.Semaphore(max_concurrent)
    
    tasks = []
    task_id = 0
    for channel_id in channel_ids:
        for token in active_tokens:
            for _ in range(tasks_per_token):
                task = asyncio.create_task(spam_task(semaphore, token, channel_id, channel_info[channel_id], contents, base_delay, proxy_list, task_id, typing_delay))
                tasks.append(task)
                task_id += 1
    
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    log_success(f"Khoi dong {len(tasks)} tasks spam...")
    log_success("Nhan Ctrl+C de dung")
    log_memory()
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log_warning("Dang dung...")
    finally:
        stop_event.set()
        cleanup_task.cancel()
        for task in online_tasks:
            task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, *online_tasks, return_exceptions=True)
        await cleanup_invalid_tokens()
        log_success("Da dung het")
        log_memory()

def main():
    def signal_handler(sig, frame):
        print(f"\n{Colors.YELLOW}[WARNING] Thoat...{Colors.RESET}")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[WARNING] Thoat...{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
