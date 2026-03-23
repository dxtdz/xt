# -*- coding: utf-8 -*-
import os
import sys
import time
import requests
import asyncio
import shutil
from colorama import Fore, Style, init

init(autoreset=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_large_text():
    large_text = """
 _____ _   _   _   _             _   _                      
|_   _| \ | | | \ | |           | \ | |                     
  | | |  \| | |  \| | _____   __|  \| | _____      _____ _ __
  | | | . ` | | . ` |/ _ \ \ / /| . ` |/ _ \ \ /\ / / _ \ '__|
 _| |_| |\  | | |\  |  __/\ V / | |\  |  __/\ V  V /  __/ |   
|_____|_| \_| |_| \_|\___| \_/  |_| \_|\___| \_/\_/ \___|_|   
                                                              
    """
    print(large_text)

def print_ryder():
    ryder_text = f"""{Fore.CYAN}
--------------------------------------------
|                                          |
| {Fore.YELLOW}Tool Copyright:  Nguyễn Đình Dương X Hbst {Fore.CYAN}|
| {Fore.YELLOW}Discord Đa token {Fore.CYAN}             |
|                                          |
--------------------------------------------
    """
    print(ryder_text)

def print_sd():
    cachsudung = f"""{Style.BRIGHT + Fore.GREEN}
Cách Sử Dụng Tool:
- B1: Chọn chế độ spam (1: Treo Ngôn | 2: Treo Nhây)
- B2: Nhập ID kênh Discord (cách nhau dấu phẩy ,)
- B3: Nhập token trực tiếp cho từng kênh
- B4: Chọn file chứa nội dung spam (file .txt)
- B5: Nhập delay cho từng token
- B6: (Mode 2) Nhập ID người réo (tag) mỗi ID 1 dòng, Enter để kết thúc
- B7: (Mode 2) Nhập tên réo (thêm tên text vào nội dung, cách nhau dấu phẩy)
    """
    print(cachsudung)

def print_boxed_menu():
    clear_screen()
    width = shutil.get_terminal_size().columns
    box_width = min(80, width - 10)

    top_border = "╔" + "═" * box_width + "╗"
    bottom_border = "╚" + "═" * box_width + "╝"
    empty_line = "║" + " " * box_width + "║"

    def print_centered(text, color=Fore.WHITE, style=Style.NORMAL):
        if len(text) > box_width:
            text = text[:box_width]
        padding_left = (box_width - len(text)) // 2
        padding_right = box_width - len(text) - padding_left
        line = "║" + " " * padding_left + f"{color}{style}{text}{Style.RESET_ALL}" + " " * padding_right + "║"
        print(line)

    print(Fore.CYAN + top_border + Style.RESET_ALL)
    print(empty_line)
    print_centered("🔥🔥🔥 TOOL SPAM DISCORD 🔥🔥🔥", Fore.MAGENTA, Style.BRIGHT)
    print(empty_line)
    print_centered("Author: Nguyễn Đình Dương X Hbst", Fore.YELLOW, Style.BRIGHT)
    print_centered("Discord đa token X HBST", Fore.YELLOW)
    print(empty_line)
    print_centered("LỰA CHỌN CHẾ ĐỘ SPAM", Fore.GREEN, Style.BRIGHT)
    print_centered("1. Treo Ngôn", Fore.GREEN)
    print_centered("2. Treo Nhây", Fore.GREEN)
    print(empty_line)
    print_centered("Nhập lựa chọn của bạn (1 hoặc 2) và Enter:", Fore.CYAN, Style.BRIGHT)
    print(empty_line)
    print(bottom_border)
    print()

def loading_animation():
    text_intro = "Đang khởi động tool, vui lòng chờ..."
    print(Fore.YELLOW + text_intro + Style.RESET_ALL)

    word = "TOOL ĐÌNH DƯƠNG"
    output = ""
    for char in word:
        output += char
        print(f"\r{Fore.GREEN}{output}{Style.RESET_ALL}", end="", flush=True)
        time.sleep(0.2)
    print()
    print(Fore.YELLOW + "Khởi động hoàn tất!\n" + Style.RESET_ALL)

def clean_line_for_hash(line):
    stripped = line.lstrip('#').lstrip()
    if stripped == "":
        return ""
    return " " + stripped

async def spam_message(token, channel_id, message, delay, spam_line_by_line=False, mention_ids=None, name_mention=None):
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    url_send = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    url_typing = f"https://discord.com/api/v9/channels/{channel_id}/typing"

    if spam_line_by_line:
        raw_lines = message.splitlines()
        messages = [clean_line_for_hash(line) for line in raw_lines]
        messages = [line for line in messages if line != ""]
    else:
        raw_lines = message.splitlines()
        cleaned_lines = [clean_line_for_hash(line) for line in raw_lines]
        messages = ["\n".join(cleaned_lines)]

    while True:
        for msg in messages:
            if spam_line_by_line:
                if mention_ids:
                    tags = " ".join(f"<@{uid}>" for uid in mention_ids)
                    msg = f"{msg} {tags}"
                if name_mention:
                    if "(name)" in msg:
                        msg = msg.replace("(name)", name_mention)
                    else:
                        msg = f"{msg} {name_mention}"

            try:
                typing_resp = requests.post(url_typing, headers=headers)
                if typing_resp.status_code == 204:
                    print(f"{Fore.MAGENTA}[Typing] Đang soạn tin ở kênh {channel_id}...")

                await asyncio.sleep(1.5)

                response = requests.post(url_send, json={"content": msg}, headers=headers)
                if response.status_code == 200:
                    print(f"{Fore.CYAN}[SUCCESS] Gửi tin nhắn tới kênh {channel_id}: {msg[:50]}{'...' if len(msg)>50 else ''}")
                elif response.status_code == 429:
                    retry_after = response.json().get("retry_after", 1)
                    print(f"{Fore.RED}[RATE LIMIT] Tạm dừng {retry_after} giây do rate limit.")
                    await asyncio.sleep(retry_after)
                else:
                    print(f"{Fore.RED}[ERROR] Lỗi {response.status_code}: {response.text}")
            except Exception as e:
                print(f"{Fore.RED}[EXCEPTION] {str(e)}")
            await asyncio.sleep(delay)

def input_mode():
    while True:
        print_boxed_menu()
        mode = input().strip()
        if mode in ["1", "2"]:
            return mode
        print(Fore.RED + "Lựa chọn không hợp lệ, vui lòng nhập lại!")

def input_channel_ids():
    raw = input(f"{Fore.CYAN}Nhập ID kênh (cách nhau dấu phẩy ,):\n").strip()
    channel_ids = [cid.strip() for cid in raw.split(",") if cid.strip()]
    if not channel_ids:
        print(f"{Fore.RED}Bạn chưa nhập ID kênh nào.")
        return input_channel_ids()
    return channel_ids

def input_tokens_for_channel(channel_id):
    print(f"{Fore.YELLOW}===== NHẬP TOKEN CHO KÊNH {channel_id} =====")
    print(f"{Fore.CYAN}Nhập token (mỗi token 1 dòng, nhập 'done' để kết thúc):")
    
    tokens = []
    token_count = 1
    while True:
        token_input = input(f"Token #{token_count}: ").strip()
        if token_input.lower() == 'done':
            if not tokens:
                print(f"{Fore.RED}Bạn chưa nhập token nào. Vui lòng nhập ít nhất 1 token!")
                continue
            break
        if token_input:
            tokens.append(token_input)
            token_count += 1
        else:
            print(f"{Fore.RED}Token không được để trống. Vui lòng nhập lại!")
    
    print(f"{Fore.GREEN}Đã nhập thành công {len(tokens)} token cho kênh {channel_id}")
    return tokens

def choose_message_file():
    txt_files = [f for f in os.listdir() if f.endswith('.txt')]
    if not txt_files:
        print(f"{Fore.RED}Không tìm thấy file .txt nào trong thư mục.")
        return choose_message_file()
    print(f"{Fore.YELLOW}Các file .txt có sẵn:")
    for idx, fname in enumerate(txt_files):
        print(f"{Fore.CYAN}{idx+1}. {fname}")
    while True:
        try:
            idx = int(input(f"{Fore.CYAN}Chọn file chứa tin nhắn (nhập số thứ tự): ")) - 1
            if 0 <= idx < len(txt_files):
                return txt_files[idx]
            else:
                print(f"{Fore.RED}Chọn file không hợp lệ. Nhập lại!")
        except ValueError:
            print(f"{Fore.RED}Vui lòng nhập số.")

def input_delay(token_idx, channel_id):
    while True:
        val = input(f"{Fore.YELLOW}Nhập delay cho token thứ {token_idx+1} (kênh {channel_id}): ").strip()
        try:
            delay = float(val)
            if delay < 0:
                print(f"{Fore.RED}Delay phải là số không âm. Nhập lại!")
                continue
            return delay
        except ValueError:
            print(f"{Fore.RED}Delay phải là số. Nhập lại!")

def input_mention_ids():
    print(f"{Fore.CYAN}Nhập từng user ID Discord để tag, Enter bỏ qua để kết thúc:")
    mention_ids = []
    while True:
        uid = input("User ID: ").strip()
        if uid == "":
            break
        mention_ids.append(uid)
    return mention_ids

def input_name_mention():
    choose_name = input(f"{Fore.CYAN}Bạn có muốn réo tên (thêm tên text vào nội dung) không? (y/n): ").strip().lower()
    if choose_name == 'y':
        names = input(f"{Fore.CYAN}Nhập tên cách nhau bởi dấu phẩy (ví dụ: Thành,Dương,Ken): ").strip()
        return ", ".join([n.strip() for n in names.split(",") if n.strip()])
    return None

def print_large_text_and_ryder():
    print_large_text()
    print_ryder()

async def main():
    print_large_text_and_ryder()
    print_sd()
    input(f"{Fore.CYAN}Nhấn Enter để tiếp tục vào menu...")
    loading_animation()

    mode = input_mode()
    spam_line_by_line = (mode == "2")

    mention_ids = []
    name_mention = None

    if spam_line_by_line:
        mention_ids = input_mention_ids()
        name_mention = input_name_mention()

    channel_ids = input_channel_ids()

    tokens_map = {}
    for ch_id in channel_ids:
        tokens_map[ch_id] = input_tokens_for_channel(ch_id)

    message_file = choose_message_file()
    with open(message_file, 'r', encoding='utf-8-sig') as f:
        message_content = f.read()

    tasks = []
    for ch_id, tokens in tokens_map.items():
        for idx, token in enumerate(tokens):
            delay = input_delay(idx, ch_id)
            tasks.append(spam_message(token, ch_id, message_content, delay, spam_line_by_line, mention_ids, name_mention))

    print(f"\n{Fore.MAGENTA}Tool thuộc quyền sở hữu của: Thành Nguyễn Đình Dương X Hbst")
    print(f"{Fore.GREEN}Đã khởi chạy {len(tasks)} task spam...\n")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
