import asyncio
import os
import re
import traceback
from urllib.parse import unquote
from playwright.async_api import async_playwright

# 替换为你想要抓取的完整链接
# 注意：如果链接中的 timestamp 或 signature 过期，你需要重新复制最新的链接
START_URL = "https://etd.xjtlu.edu.cn/"

# 获取桌面路径
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

async def main():
    async with async_playwright() as p:
        # headless=False 会弹出浏览器窗口，方便你手动登录（如果需要）
        print("正在启动浏览器...")
        
        browser = None
        try:
            print("尝试启动 Microsoft Edge...")
            browser = await p.chromium.launch(headless=False, channel="msedge")
        except Exception:
            try:
                print("Edge 启动失败，尝试启动 Google Chrome...")
                browser = await p.chromium.launch(headless=False, channel="chrome")
            except Exception:
                print("系统浏览器启动失败，尝试启动 Playwright 内置 Chromium...")
                browser = await p.chromium.launch(headless=False)
        
        # 创建上下文，这样可以监听所有标签页（包括新弹出的）
        context = await browser.new_context()
        page = await context.new_page()

        print(f"正在打开页面: {START_URL}")
        
        # 用于存储已下载的 URL，防止重复下载
        downloaded_urls = set()
        
        # 监听网络响应，寻找 PDF 文件
        async def handle_response(resp):
            try:
                url = resp.url
                # 如果这个 URL 已经下载过，直接跳过
                if url in downloaded_urls:
                    return

                lower_url = url.lower()
                headers = resp.headers
                content_type = headers.get("content-type", "").lower()
                status = resp.status

                # 忽略一些明显无关的资源
                if any(ext in lower_url for ext in ['.js', '.css', '.png', '.jpg', '.ico', '.woff', '.json']):
                    return

                # 检查是否可能是 PDF 的响应
                is_target = False
                if "browserfile" in lower_url:
                    is_target = True
                elif "application/pdf" in content_type:
                    is_target = True
                elif lower_url.endswith(".pdf"):
                    is_target = True
                elif "octet-stream" in content_type and "viewer.html" not in lower_url:
                    is_target = True

                if is_target and status in (200, 206):
                    try:
                        body = await resp.body()
                        # 检查文件头是否为 %PDF
                        if body and body.startswith(b'%PDF'):
                            # 标记为已下载
                            downloaded_urls.add(url)
                            
                            # 尝试从 Content-Disposition 获取文件名
                            content_disposition = headers.get("content-disposition", "")
                            detected_name = "unknown_paper.pdf"
                            
                            if "filename=" in content_disposition:
                                # 简单的正则提取文件名
                                match = re.search(r'filename\*?=?(?:UTF-8\'\')?"?([^";\n]+)"?', content_disposition)
                                if match:
                                    detected_name = unquote(match.group(1))
                            
                            # 清理文件名中的非法字符
                            detected_name = re.sub(r'[\\/*?:"<>|]', "_", detected_name)
                            if not detected_name.lower().endswith(".pdf"):
                                detected_name += ".pdf"
                            
                            # 处理重名文件
                            save_path = os.path.join(desktop_path, detected_name)
                            counter = 1
                            base_name, ext = os.path.splitext(detected_name)
                            while os.path.exists(save_path):
                                save_path = os.path.join(desktop_path, f"{base_name}({counter}){ext}")
                                counter += 1

                            # 保存文件
                            with open(save_path, "wb") as f:
                                f.write(body)
                                
                            print(f"\n>>> [成功] 已下载: {os.path.basename(save_path)}")
                            print(f"    URL: {url}")
                            print(f"    大小: {len(body)} 字节")
                            print(">>> 请继续点击下一个试卷链接...")
                            
                    except Exception as e:
                        # 忽略读取失败的
                        pass

            except Exception as e:
                pass

        # 监听整个上下文的响应（包含所有新开标签页）
        context.on("response", handle_response)

        try:
            # 访问页面
            await page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"页面加载可能超时或出错，继续等待 PDF: {e}")

        print(">>> 脚本正在运行中 (批量模式)...")
        print(">>> 请在弹出的浏览器窗口中操作：")
        print("    1. 登录学校网站。")
        print("    2. 依次点击你想下载的试卷链接（支持多标签页）。")
        print("    3. 脚本会自动检测并下载所有打开的 PDF 到桌面。")
        print("    4. 下载完成后，请手动关闭浏览器窗口，脚本会自动退出。")
        
        # 保持运行，直到浏览器被关闭
        while context.pages:
            await asyncio.sleep(1)
        
        print(">>> 浏览器已关闭，脚本退出。")
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n>>> 用户停止脚本。")
    except Exception as e:
        print(f"\n>>> 发生严重错误: {e}")
        traceback.print_exc()
    finally:
        input("\n>>> 程序运行结束，按回车键退出...")