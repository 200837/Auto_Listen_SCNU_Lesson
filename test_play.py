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

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()

    # 抓上报请求
    uploads = []
    def on_request(req):
        if 'mod_fsresource_set_time' in req.url or 'service.php' in req.url:
            try:
                uploads.append({"url": req.url, "body": req.post_data})
            except Exception:
                uploads.append({"url": req.url, "body": None})
    page.on("request", on_request)

    sso_login(page)

    # 打开一个未完成视频：876917
    page.goto("https://moodle.scnu.edu.cn/mod/fsresource/view.php?id=876917", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # 观察播放器状态
    info = page.evaluate("""() => {
        const v = document.querySelector('#fsplayer-container-id_html5_api');
        const dur = document.querySelector('.vjs-duration-display');
        return {
            videoExists: !!v,
            src: v ? v.src : null,
            readyState: v ? v.readyState : null,
            duration: v ? v.duration : null,
            durationDisplay: dur ? dur.textContent : null,
            currentTime: v ? v.currentTime : null,
            paused: v ? v.paused : null,
        };
    }""")
    print("播放器初始状态:", json.dumps(info, ensure_ascii=False))

    # 点击播放
    try:
        page.click(".vjs-big-play-button", timeout=8000)
    except Exception as e:
        print("点击大播放按钮失败，尝试 video.play():", e)
        page.evaluate("() => { const v = document.querySelector('#fsplayer-container-id_html5_api'); v.muted = true; v.play(); }")

    # 观察 30 秒
    for i in range(6):
        page.wait_for_timeout(5000)
        st = page.evaluate("""() => {
            const v = document.querySelector('#fsplayer-container-id_html5_api');
            const cur = document.querySelector('.vjs-current-time-display');
            const bfjd = document.querySelector('.num-bfjd span');
            return {ct: v ? v.currentTime : null, paused: v ? v.paused : null,
                    ctDisplay: cur ? cur.textContent : null,
                    progress: bfjd ? bfjd.textContent : null};
        }""")
        print(f"[{i*5+5}s] ", json.dumps(st, ensure_ascii=False))

    print("\n=== 上报请求 ===")
    for u in uploads:
        print(u['url'][-80:], "|", (u['body'] or '')[:300])

    browser.close()
