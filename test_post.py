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

    # 抓课程视频列表
    page.goto("https://moodle.scnu.edu.cn/course/view.php?id=19922", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    videos = page.evaluate("""() => {
        const out = []; const seen = new Set();
        document.querySelectorAll('li.activity').forEach(li => {
            const a = li.querySelector('a[href*="mod/fsresource/view.php?id="]');
            if (!a) return;
            const m = a.href.match(/id=(\\d+)/); if (!m) return;
            const id = m[1]; if (seen.has(id)) return; seen.add(id);
            const name = (li.querySelector('.instancename')?.textContent || a.textContent || '').trim();
            const ci = li.querySelector('.completioninfo');
            const dv = ci ? ci.getAttribute('data-value') : null;
            out.push({id, name, dv});
        });
        return out;
    }""")
    print("总视频数:", len(videos))
    incomplete = [v for v in videos if v['dv'] == '0']
    print("未完成视频数:", len(incomplete))
    for v in incomplete[:5]:
        print("  ", v)

    # 取 sesskey
    sesskey = page.evaluate("typeof M !== 'undefined' && M.cfg && M.cfg.sesskey ? M.cfg.sesskey : ''")
    print("sesskey:", sesskey)

    # 挑第一个未完成视频，GET view 页提取 fsresourceid
    target = incomplete[0]
    cmid = target['id']
    print("\n测试目标:", target)
    page.goto(f"https://moodle.scnu.edu.cn/mod/fsresource/view.php?id={cmid}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    html = page.content()
    m_fs = re.search(r"'fsresourceid'\s*:\s*(\d+)", html)
    m_prog = re.search(r"'progress'\s*:\s*(\d+)", html)
    m_sess = re.search(r"'sesskey'\s*:\s*'([^']+)'", html)
    print("fsresourceid:", m_fs.group(1) if m_fs else None)
    print("当前progress:", m_prog.group(1) if m_prog else None)
    if m_sess:
        sesskey = m_sess.group(1)
        print("页面sesskey:", sesskey)

    fsid = m_fs.group(1)

    # 尝试 POST set_time
    import time as _t
    ts = int(_t.time() * 1000)
    url = f"https://moodle.scnu.edu.cn/lib/ajax/service.php?timestamp={ts}&sesskey={sesskey}"
    payload = [{"index":0,"methodname":"mod_fsresource_set_time",
                "args":{"fsresourceid":int(fsid),"time":1,"finish":1,"progress":100,
                        "unique":f"test_{int(_t.time()*1000)}"}}]
    resp = page.evaluate("""async ([url, payload]) => {
        const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        return await r.text();
    }""", [url, payload])
    print("\n=== POST 返回 ===")
    print(resp)

    # 重新加载 view 页看 progress 是否变 100
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    html2 = page.content()
    m_prog2 = re.search(r"'progress'\s*:\s*(\d+)", html2)
    print("刷后 progress:", m_prog2.group(1) if m_prog2 else None)

    browser.close()
