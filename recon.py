import io, sys, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

USER = "202639024285"
PWD = "QF9098aa!"

def find_confirm_link(page):
    # 遍历所有 a 元素，找 innerText 含"确定登录"的
    links = page.query_selector_all('a')
    for a in links:
        try:
            t = a.inner_text()
        except Exception:
            continue
        if t and '确定登录' in t:
            return a
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()

    # 1. 进入登录页
    page.goto("https://moodle.scnu.edu.cn/login/index.php", wait_until="domcontentloaded", timeout=60000)
    # 点统一身份认证链接
    page.click("a[href*='sso.scnu.edu.cn']", timeout=15000)
    page.wait_for_load_state("domcontentloaded")
    # 等待跳转到 sso 登录页
    for _ in range(20):
        if 'sso.scnu.edu.cn' in page.url and 'login.html' in page.url:
            break
        page.wait_for_timeout(500)
    print("SSO登录页URL:", page.url)

    # 2. 填账号密码提交
    page.fill("#account", USER)
    page.fill("#password", PWD)
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('#login-form-password').submit()")
    page.wait_for_load_state("domcontentloaded")
    for _ in range(30):
        if 'moodle.scnu.edu.cn' in page.url:
            break
        page.wait_for_timeout(500)
    print("提交后URL:", page.url)

    # 3. 如果还在确认页，点确定登录
    if 'auth.html' in page.url or 'fastlogin' in page.url or 'sysname' in page.url:
        # JS 直接调用确认登录的跳转函数（绕过可见性检查）
        try:
            page.evaluate("typeof gotoApp === 'function' && gotoApp()")
        except Exception as e:
            print("gotoApp调用异常:", e)
        for _ in range(40):
            if 'moodle.scnu.edu.cn' in page.url:
                break
            page.wait_for_timeout(500)
        print("点击确定后URL:", page.url)

    # 等待最终落地
    page.wait_for_timeout(2000)
    print("最终URL:", page.url)

    # 4. 抓取课程列表
    if '/my/' not in page.url:
        page.goto("https://moodle.scnu.edu.cn/my/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

    # 抓课程链接
    links = page.query_selector_all("a[href*='course/view.php?id=']")
    seen = {}
    for a in links:
        href = a.get_attribute('href') or ''
        m = re.search(r'id=(\d+)', href)
        if not m:
            continue
        cid = m.group(1)
        txt = (a.inner_text() or '').strip()
        if cid not in seen:
            seen[cid] = txt
    print("\n=== 课程列表 (共 %d 个) ===" % len(seen))
    for cid, txt in seen.items():
        print(f"id={cid}  名称={txt}")

    # 也抓取 block 里可能出现的课程卡片
    body = page.content()
    print("\nmy/页面里 course/view.php 出现次数:", body.count('course/view.php'))
    print("my/页面里 my-course 相关:", 'my-course' in body, 'course-box' in body, 'dashboard' in body)

    browser.close()
