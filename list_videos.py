import io, sys, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

USER = "202639024285"
PWD = "QF9098aa!"

def sso_login(page):
    page.goto("https://moodle.scnu.edu.cn/login/index.php", wait_until="domcontentloaded", timeout=60000)
    page.click("a[href*='sso.scnu.edu.cn']", timeout=15000)
    page.wait_for_load_state("domcontentloaded")
    for _ in range(20):
        if 'sso.scnu.edu.cn' in page.url and 'login.html' in page.url:
            break
        page.wait_for_timeout(500)
    page.fill("#account", USER)
    page.fill("#password", PWD)
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('#login-form-password').submit()")
    page.wait_for_load_state("domcontentloaded")
    for _ in range(30):
        if 'moodle.scnu.edu.cn' in page.url:
            break
        page.wait_for_timeout(500)
    if 'auth.html' in page.url or 'fastlogin' in page.url or 'sysname' in page.url:
        try:
            page.evaluate("typeof gotoApp === 'function' && gotoApp()")
        except Exception:
            pass
        for _ in range(40):
            if 'moodle.scnu.edu.cn' in page.url:
                break
            page.wait_for_timeout(500)
    page.wait_for_timeout(1500)
    return page.url

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    sso_login(page)
    print("登录后URL:", page.url)

    page.goto("https://moodle.scnu.edu.cn/course/view.php?id=19922", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    # 用 courseindex 遍历：li.courseindex-item 里配对 link + completioninfo
    videos = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('li.courseindex-item').forEach(li => {
            const a = li.querySelector('a.courseindex-link[href*="mod/fsresource/view.php?id="]');
            if (!a) return;
            const m = a.href.match(/id=(\\d+)/); if (!m) return;
            const id = m[1];
            const ci = li.querySelector('.completioninfo');
            const dv = ci ? ci.getAttribute('data-value') : null;
            const name = (a.textContent || '').trim();
            out.push({id, name, dv});
        });
        return out;
    }""")
    print("总视频数:", len(videos))
    incomplete = [v for v in videos if v['dv'] == '0']
    complete = [v for v in videos if v['dv'] == '1']
    print("已完成:", len(complete), " 未完成:", len(incomplete))
    for v in incomplete:
        print("  未完成:", v['id'], v['name'])

    browser.close()
