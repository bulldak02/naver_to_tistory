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
import subprocess  # macOS 클립보드 처리를 위해 추가
import tempfile    # macOS 임시 파일 처리를 위해 추가

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

# 윈도우 환경일 경우에만 윈도우 전용 모듈 임포트
if sys.platform == "win32":
    import winsound
    import win32clipboard

class BlogMigratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("네이버 -> 티스토리 마이그레이션 (SEO Alt 텍스트 적용)")
        self.root.geometry("550x700")
        self.driver = None
        self.setup_ui()
        # --- 창 닫기 버튼(X) 이벤트 연결 ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

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

    def combine_images_horizontally(self, img_paths, output_path):
        try:
            images = [Image.open(p) for p in img_paths]
            min_height = min(img.height for img in images)
            
            resized_images = []
            for img in images:
                new_width = int(img.width * (min_height / img.height))
                resized_images.append(img.resize((new_width, min_height), Image.Resampling.LANCZOS))
            
            total_width = sum(img.width for img in resized_images)
            combined_img = Image.new('RGB', (total_width, min_height), (255, 255, 255))
            
            x_offset = 0
            for img in resized_images:
                combined_img.paste(img, (x_offset, 0))
                x_offset += img.width
                
            combined_img.save(output_path, 'JPEG', quality=95)
            return True
        except Exception as e:
            self.log(f"❌ 이미지 합성 오류: {e}")
            return False

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
            
            components = soup.find_all('div', class_='se-component')
            
            for comp in components:
                classes = comp.get('class', [])
                
                if 'se-table' in classes:
                    table_tag = comp.find('table')
                    if table_tag:
                        table_tag['style'] = "border-collapse: collapse; width: 100%; text-align: center; margin: 0; font-family: 'Malgun Gothic', sans-serif;"
                        for cell in table_tag.find_all(['th', 'td']):
                            cell['style'] = "border: 1px solid #dddddd; padding: 12px; background-color: #ffffff; color: #333;"
                        elements.append({'type': 'table', 'content': str(table_tag)})
                        
                elif 'se-quote' in classes:
                    text = comp.get_text(separator='\n', strip=True)
                    if text:
                        html_str = f"<blockquote data-ke-style='style1' style='margin-bottom: 15px;'>{text.replace(chr(10), '<br>')}</blockquote>"
                        elements.append({'type': 'html', 'content': html_str})
                        
                elif 'se-text' in classes:
                    text = comp.get_text(separator='\n', strip=True)
                    if text: 
                        elements.append({'type': 'text', 'content': text})
                        
                elif any('image' in c.lower() for c in classes):
                    imgs = comp.find_all('img')
                    urls = []
                    for img in imgs:
                        src = img.get('data-lazy-src') or img.get('data-src') or img.get('src')
                        if src:
                            if src.startswith('//'): src = 'https:' + src
                            if 'type=' in src: src = re.sub(r'type=[a-zA-Z0-9_]+', 'type=w966', src)
                            urls.append(src)
                    
                    if len(urls) > 1:
                        elements.append({'type': 'image_group', 'urls': urls})
                    elif len(urls) == 1:
                        elements.append({'type': 'image', 'url': urls[0]})

                elif 'se-file' in classes:
                    a_tag = comp.find('a')
                    if a_tag and a_tag.get('href'):
                        file_url = a_tag.get('href')
                        file_name = "첨부파일_다운로드"
                        for text_node in comp.stripped_strings:
                            if '.' in text_node and len(text_node) > 3:
                                file_name = text_node
                                break
                        elements.append({'type': 'file', 'url': file_url, 'name': file_name})
                
            return title, elements
        except Exception as e:
            self.log(f"❌ 크롤링 오류: {e}")
            return None, []

    def send_image_to_clipboard(self, filepath):
        """운영체제에 맞게 이미지를 클립보드로 복사합니다."""
        try:
            if sys.platform == "win32":
                # Windows 전용 처리
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
                
            elif sys.platform == "darwin":
                # macOS 전용 처리 (osascript 활용)
                image = Image.open(filepath)
                # AppleScript 호환성을 위해 임시 JPEG 파일로 변환
                temp_path = os.path.join(tempfile.gettempdir(), "temp_mac_clip.jpg")
                image.convert("RGB").save(temp_path, "JPEG")
                
                script = f'set the clipboard to (read (POSIX file "{temp_path}") as JPEG picture)'
                subprocess.run(['osascript', '-e', script], check=True)
                return True
                
        except Exception as e:
            self.log(f"이미지 클립보드 복사 실패: {e}")
            return False

    def download_image(self, url, save_path):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://blog.naver.com/"
        }
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and len(res.content) > 0:
                with open(save_path, 'wb') as f:
                    f.write(res.content)
                return True
            else:
                self.log(f"⚠️ 이미지 다운로드 실패 (응답 코드: {res.status_code})")
                return False
        except Exception as e:
            self.log(f"⚠️ 이미지 다운로드 에러: {e}")
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

        # 표(table) 요소 이미지 캡처 처리
        for idx, el in enumerate(elements):
            if el['type'] == 'table':
                html_path = os.path.join(temp_dir, f"temp_table_{naver_no}_{idx}.html")
                img_path = os.path.join(temp_dir, f"table_img_{naver_no}_{idx}.png")
                
                html_content = f"""
                <!DOCTYPE html>
                <html><head><meta charset="utf-8">
                <style>body {{ padding: 20px; background-color: white; display: inline-block; }}</style>
                </head><body>{el['content']}</body></html>
                """
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
                self.driver.get(file_url)
                time.sleep(0.5)
                
                try:
                    table_elem = self.driver.find_element(By.TAG_NAME, "table")
                    table_elem.screenshot(img_path) 
                    el['type'] = 'local_image'
                    el['path'] = img_path
                except Exception as e:
                    self.log(f"⚠️ 표 캡처 실패: {e}")
                    el['type'] = 'text'
                    el['content'] = "[표 캡처 실패]"
                
                try: os.remove(html_path) 
                except: pass
        
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
            
            cursor_to_end_js = """
            var el = arguments[0];
            if(el) {
                el.focus();
                var range = document.createRange();
                var sel = window.getSelection();
                range.selectNodeContents(el);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
            }
            """

            img_count = 1
            # 🚀 중복 제거 및 깔끔하게 통합된 본문 작성 루프
            for el in elements:
                self.driver.execute_script(cursor_to_end_js, active_element)
                time.sleep(0.2)
                
                # 1. 일반 텍스트 처리
                if el['type'] == 'text':
                    pyperclip.copy(el['content'])
                    active_element.send_keys(paste_key, 'v')
                    time.sleep(0.3)
                    active_element.send_keys(Keys.ENTER)
                    time.sleep(0.2)
                    
                # 2. 인용구 처리
                elif el['type'] == 'html':
                    safe_html = el['content'] + "<p><br></p>"
                    self.driver.execute_script("document.execCommand('insertHTML', false, arguments[0]);", safe_html)
                    time.sleep(0.5)
                    self.driver.execute_script(cursor_to_end_js, active_element)
                    active_element.send_keys(Keys.ENTER)
                    time.sleep(0.2)
                    
                # 3. 첨부파일 처리 
                elif el['type'] == 'file':
                    file_path = os.path.join(temp_dir, el['name'])
                    try:
                        file_res = requests.get(el['url'], headers={"User-Agent": "Mozilla/5.0"})
                        with open(file_path, 'wb') as f:
                            f.write(file_res.content)
                        self.log(f"💾 첨부파일 PC 백업 완료: {el['name']}")
                    except Exception as e:
                        self.log(f"⚠️ 첨부파일 PC 저장 실패 (링크만 생성): {e}")

                    file_text = f"💾 첨부파일 다운로드: {el['name']}\n{el['url']}\n"
                    pyperclip.copy(file_text)
                    active_element.send_keys(paste_key, 'v')
                    time.sleep(0.5)
                    
                    self.driver.execute_script(cursor_to_end_js, active_element)
                    active_element.send_keys(Keys.ENTER)
                    time.sleep(0.2)
                    
                # 4. 표 이미지 삽입
                elif el['type'] == 'local_image':
                    if self.send_image_to_clipboard(el['path']):
                        active_element.send_keys(paste_key, 'v')
                        time.sleep(4.0) 
                        
                        reset_font_js = """
                        var editor = arguments[0];
                        if (editor) {
                            var imgs = editor.querySelectorAll('img');
                            if (imgs.length > 0) {
                                var lastImg = imgs[imgs.length - 1];
                                var targetNode = lastImg.closest('figure') || lastImg.parentElement;
                                var p = document.createElement('p');
                                p.innerHTML = '<br>';
                                targetNode.after(p);
                                
                                var range = document.createRange();
                                var sel = window.getSelection();
                                range.selectNodeContents(p);
                                range.collapse(true);
                                sel.removeAllRanges();
                                sel.addRange(range);
                            }
                        }
                        """
                        self.driver.execute_script(reset_font_js, active_element)
                        time.sleep(0.3)
                        
                        alt_text = f"{title} - 내용 정리 표 {img_count}"
                        js_script = """
                        var editor = arguments[0];
                        if (editor) {
                            var imgs = editor.querySelectorAll('img');
                            if (imgs.length > 0) {
                                var lastImg = imgs[imgs.length - 1];
                                lastImg.setAttribute('alt', arguments[1]);
                                lastImg.setAttribute('data-alt', arguments[1]);
                            }
                        }
                        """
                        self.driver.execute_script(js_script, active_element, alt_text)
                        self.log(f"✅ 표 캡처 이미지 {img_count} 삽입 및 SEO Alt 입력 완료")
                        img_count += 1
                        
                # 5. 일반 단일 이미지 삽입
                elif el['type'] == 'image':
                    img_path = os.path.join(temp_dir, f"img_{naver_no}_{img_count}.jpg")
                    if self.download_image(el['url'], img_path):
                        if self.send_image_to_clipboard(img_path):
                            active_element.send_keys(paste_key, 'v')
                            time.sleep(3.5)
                            
                            self.driver.execute_script(cursor_to_end_js, active_element)
                            active_element.send_keys(Keys.ENTER)
                            time.sleep(0.3)
                            
                            alt_text = f"{title} - 사진 {img_count}"
                            js_script = """
                            var editor = arguments[0];
                            if (editor) {
                                var imgs = editor.querySelectorAll('img');
                                if (imgs.length > 0) {
                                    var lastImg = imgs[imgs.length - 1];
                                    lastImg.setAttribute('alt', arguments[1]);
                                    lastImg.setAttribute('data-alt', arguments[1]);
                                }
                            }
                            """
                            self.driver.execute_script(js_script, active_element, alt_text)
                            self.log(f"✅ 사진 {img_count}에 SEO 대체 텍스트 삽입 완료")
                    img_count += 1
                    
                # 6. 나란히 그룹 이미지 삽입
                elif el['type'] == 'image_group':
                    group_paths = []
                    for idx, u in enumerate(el['urls']):
                        sub_path = os.path.join(temp_dir, f"img_{naver_no}_{img_count}_sub_{idx}.jpg")
                        if self.download_image(u, sub_path):
                            group_paths.append(sub_path)
                    
                    if group_paths:
                        combined_path = os.path.join(temp_dir, f"img_{naver_no}_{img_count}_combined.jpg")
                        if self.combine_images_horizontally(group_paths, combined_path):
                            if self.send_image_to_clipboard(combined_path):
                                active_element.send_keys(paste_key, 'v')
                                time.sleep(3.5)
                                
                                self.driver.execute_script(cursor_to_end_js, active_element)
                                active_element.send_keys(Keys.ENTER)
                                time.sleep(0.3)
                                
                                alt_text = f"{title} - 나란히 사진 {img_count}"
                                js_script = """
                                var editor = arguments[0];
                                if (editor) {
                                    var imgs = editor.querySelectorAll('img');
                                    if (imgs.length > 0) {
                                        var lastImg = imgs[imgs.length - 1];
                                        lastImg.setAttribute('alt', arguments[1]);
                                        lastImg.setAttribute('data-alt', arguments[1]);
                                    }
                                }
                                """
                                self.driver.execute_script(js_script, active_element, alt_text)
                                self.log(f"✅ 나란히 사진 그룹 {img_count} 합성 및 SEO Alt 입력 완료")
                    img_count += 1
            
            self.log("🎉 원본 크기 사진, 표 캡처, 텍스트 분리, 첨부파일 링크까지 완벽하게 입력되었습니다!")
            
            # OS별 알림음 분기 처리
            if sys.platform == "win32":
                winsound.MessageBeep(winsound.MB_OK)
            else:
                self.root.bell()
                
            self.root.after(0, lambda: messagebox.showinfo(
                "작업 완료", 
                "🎉 모든 요소(첨부파일 링크 포함)가 완벽하게 입력되었습니다!"
            ))
            
        except Exception as e:
            self.log(f"❌ 티스토리 작성 중 오류 발생: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BlogMigratorApp(root)
    root.mainloop()