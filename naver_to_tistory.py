import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import requests
import pyperclip
import time
import sys
import os
import re
import io
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from PIL import Image
import win32clipboard

class BlogMigratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("네이버 -> 티스토리 마이그레이션 (SEO Alt 텍스트 적용)")
        self.root.geometry("550x700")
        self.driver = None
        self.setup_ui()

    def setup_ui(self):
        frame_login = tk.LabelFrame(self.root, text="1단계: 티스토리 로그인", padx=10, pady=5)
        frame_login.pack(fill="x", padx=10, pady=5)
        tk.Button(frame_login, text="브라우저 열기 (수동 로그인)", command=self.open_browser, height=2).pack(fill="x")
        
        frame_info = tk.LabelFrame(self.root, text="2단계: 블로그 정보 입력 및 글 선택", padx=10, pady=10)
        frame_info.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_info, text="네이버 아이디:").grid(row=0, column=0, sticky="w", pady=2)
        self.entry_naver_id = tk.Entry(frame_info, width=20)
        self.entry_naver_id.grid(row=0, column=1, sticky="w", pady=2)
        tk.Button(frame_info, text="최근 글 목록 불러오기", command=self.fetch_rss_list).grid(row=0, column=2, padx=5)
        
        self.tree = ttk.Treeview(frame_info, columns=("log_no", "title"), show="headings", height=5)
        self.tree.heading("log_no", text="글 번호")
        self.tree.heading("title", text="제목")
        self.tree.column("log_no", width=100, anchor="center")
        self.tree.column("title", width=350, anchor="w")
        self.tree.grid(row=1, column=0, columnspan=3, pady=5)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        tk.Label(frame_info, text="네이버 글 번호:").grid(row=3, column=0, sticky="w", pady=10)
        self.entry_naver_no = tk.Entry(frame_info, width=35)
        self.entry_naver_no.grid(row=3, column=1, columnspan=2, sticky="w", pady=10)
        
        tk.Label(frame_info, text="티스토리 주소명:").grid(row=4, column=0, sticky="w", pady=2)
        self.entry_tistory_name = tk.Entry(frame_info, width=35)
        self.entry_tistory_name.grid(row=4, column=1, columnspan=2, sticky="w", pady=2)
        
        tk.Button(self.root, text="글 가져오기 및 작성 (사진 포함)", command=self.start_migration, height=2, bg="#4CAF50", fg="white").pack(fill="x", padx=10, pady=5)
        
        self.txt_log = scrolledtext.ScrolledText(self.root, height=8, state="disabled")
        self.txt_log.pack(fill="both", padx=10, pady=5, expand=True)

    def log(self, message):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")
        self.root.update()

    def open_browser(self):
        if self.driver is not None:
            messagebox.showinfo("알림", "이미 브라우저가 열려있습니다.")
            return
        def run():
            self.log("크롬 브라우저를 실행합니다...")
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            self.driver.get("https://www.tistory.com/auth/login")
            self.log("✅ 브라우저가 열렸습니다. 로그인 후 진행해주세요.")
        threading.Thread(target=run, daemon=True).start()

    def fetch_rss_list(self):
        naver_id = self.entry_naver_id.get().strip()
        if not naver_id: return
        def run_rss():
            try:
                response = requests.get(f"https://rss.blog.naver.com/{naver_id}.xml", timeout=5)
                root = ET.fromstring(response.text)
                for i in self.tree.get_children(): self.tree.delete(i)
                for item in root.findall('./channel/item'):
                    title = item.find('title').text
                    match = re.search(r'(?:logNo=|/)(\d+)', item.find('link').text)
                    if match: self.tree.insert('', 'end', values=(match.group(1), title))
                self.log("✅ 최근 글 목록을 불러왔습니다.")
            except Exception as e:
                self.log(f"❌ RSS 파싱 오류: {e}")
        threading.Thread(target=run_rss, daemon=True).start()

    def on_tree_double_click(self, event):
        selected = self.tree.selection()
        if selected:
            self.entry_naver_no.delete(0, tk.END)
            self.entry_naver_no.insert(0, self.tree.item(selected[0], "values")[0])


    def get_naver_post_sequential(self, blog_id, log_no):
        url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title_elem = soup.find('div', class_='se-title-text')
            if not title_elem: return None, []
            
            title = title_elem.get_text(strip=True)
            elements = []
            
            components = soup.find_all('div', class_=re.compile(r'se-component\b'))
            for comp in components:
                classes = comp.get('class', [])
                if 'se-text' in classes:
                    text = comp.get_text(separator='\n', strip=True)
                    if text: elements.append({'type': 'text', 'content': text})
                elif 'se-image' in classes:
                    img = comp.find('img')
                    if img:
                        src = img.get('data-lazy-src') or img.get('data-src') or img.get('src')
                        if src:
                            if src.startswith('//'):
                                src = 'https:' + src
                            if 'type=' in src:
                                src = re.sub(r'type=[a-zA-Z0-9_]+', 'type=w966', src)
                                
                            elements.append({'type': 'image', 'url': src})
                        
            return title, elements
        except Exception as e:
            self.log(f"❌ 크롤링 오류: {e}")
            return None, []

    def send_image_to_clipboard(self, filepath):
        try:
            image = Image.open(filepath)
            output = io.BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:] 
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            self.log(f"이미지 클립보드 복사 실패: {e}")
            return False

    def start_migration(self):
        naver_id = self.entry_naver_id.get().strip()
        naver_no = self.entry_naver_no.get().strip()
        tistory_name = self.entry_tistory_name.get().strip()
        
        if not all([naver_id, naver_no, tistory_name]): return
        if self.driver is None: return
            
        threading.Thread(target=self.run_migration, args=(naver_id, naver_no, tistory_name), daemon=True).start()

    def run_migration(self, naver_id, naver_no, tistory_name):
        self.log(f"[{naver_no}] 네이버 글 추출 시작...")
        title, elements = self.get_naver_post_sequential(naver_id, naver_no)
        
        if not title or not elements:
            self.log("❌ 글 추출 실패.")
            return
            
        self.log(f"✅ 추출 성공! 총 {len(elements)}개의 요소를 발견했습니다.")
        
        temp_dir = os.path.join(os.getcwd(), "naver_temp_images")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            self.driver.get(f"https://{tistory_name}.tistory.com/manage/post")
            wait = WebDriverWait(self.driver, 10)
            
            try:
                WebDriverWait(self.driver, 3).until(EC.alert_is_present()).dismiss()
            except TimeoutException:
                pass
            
            title_input = wait.until(EC.presence_of_element_located((By.ID, "post-title-inp")))
            title_input.clear()
            title_input.send_keys(title)
            
            title_input.click()
            time.sleep(0.5)
            title_input.send_keys(Keys.TAB)
            time.sleep(1)
            
            active_element = self.driver.switch_to.active_element
            paste_key = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
            
            img_count = 1
            for el in elements:
                if el['type'] == 'text':
                    pyperclip.copy(el['content'])
                    active_element.send_keys(paste_key, 'v')
                    active_element.send_keys(Keys.ENTER)
                    time.sleep(0.5)
                    
                elif el['type'] == 'image':
                    img_path = os.path.join(temp_dir, f"img_{naver_no}_{img_count}.jpg")
                    res = requests.get(el['url'])
                    with open(img_path, 'wb') as f:
                        f.write(res.content)
                        
                    if self.send_image_to_clipboard(img_path):
                        active_element.send_keys(paste_key, 'v')
                        
                        time.sleep(3.5) # 사진 업로드 대기
                        
                        # 1. 캡션(설명란) 빠져나오기
                        active_element.send_keys(Keys.DOWN)
                        time.sleep(0.3)
                        active_element.send_keys(Keys.ENTER)
                        time.sleep(0.5)
                        
                        # 2. 🚀 [핵심 추가] 백그라운드 스크립트로 마지막 이미지에 Alt 텍스트 강제 주입
                        alt_text = f"{title} - 사진 {img_count}"
                        js_script = """
                        var editor = document.querySelector('[contenteditable="true"]');
                        if (editor) {
                            var imgs = editor.querySelectorAll('img');
                            if (imgs.length > 0) {
                                var lastImg = imgs[imgs.length - 1];
                                lastImg.setAttribute('alt', arguments[0]);
                                lastImg.setAttribute('data-alt', arguments[0]); // 티스토리 자체 호환 속성
                            }
                        }
                        """
                        self.driver.execute_script(js_script, alt_text)
                        self.log(f"✅ 사진 {img_count}에 SEO 대체 텍스트 삽입 완료: '{alt_text}'")
                    
                    img_count += 1
            
            self.log("🎉 원본 크기 사진, 텍스트 분리, SEO Alt 태그까지 완벽하게 입력되었습니다!")
            
        except Exception as e:
            self.log(f"❌ 티스토리 작성 중 오류 발생: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BlogMigratorApp(root)
    root.mainloop()
