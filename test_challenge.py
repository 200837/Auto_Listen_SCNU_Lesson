import io, sys, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

USER = "202639024285"
PWD = "QF9098aa!"
BASE = "https://moodle.scnu.edu.cn"

def sso_login(page):
    page.goto(f"{BASE}/login/index.php", wait_until="domcontentloaded", timeout=60000)
    try:
        page.click("a[href*='sso.scnu.edu.cn']", timeout=15000)
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded")
    for _ in range(30):
        if 'sso.scnu.edu.cn' in page.url and 'login.html' in page.url:
            break
        page.wait_for_timeout(500)
    page.fill("#account", USER)
    page.fill("#password", PWD)
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('#login-form-password').submit()")
    page.wait_for_load_state("domcontentloaded")
    for _ in range(40):
        if 'moodle.scnu.edu.cn' in page.url:
            break
        page.wait_for_timeout(500)
    if 'auth.html' in page.url or 'fastlogin' in page.url or 'sysname' in page.url:
        try:
            page.evaluate("typeof gotoApp === 'function' && gotoApp()")
        except Exception:
            pass
        for _ in range(50):
            if 'moodle.scnu.edu.cn' in page.url:
                break
            page.wait_for_timeout(500)
    page.wait_for_timeout(2000)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    sso_login(page)
    page.goto(f"{BASE}/mod/fsresource/view.php?id=876917", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)

    probe = page.evaluate("""() => {
        const r = {};
        r.hasPlayerWrapper = typeof playerWrapper !== 'undefined';
        r.playerWrapperType = typeof playerWrapper;
        if (typeof playerWrapper !== 'undefined') {
            r.videoDuration = playerWrapper.videoDuration;
            r.antiBot = playerWrapper.antiBot;
            r.hasOpenHumanChallenge = typeof playerWrapper.openHumanChallenge === 'function';
        }
        return r;
    }""")
    print("probe:", json.dumps(probe, ensure_ascii=False))

    # 检查 openHumanChallenge 内部依赖
    r = page.evaluate("""() => {
        try {
            playerWrapper.videoDuration = 2000; // 33分钟
            playerWrapper.antiBot.requiresChallenge = true;
            playerWrapper.antiBot.challengeOpen = false;
            playerWrapper.openHumanChallenge();
            return 'called-ok';
        } catch(e) { return 'err:'+e.message; }
    }""")
    print("手动调用结果:", r)
    page.wait_for_timeout(800)
    has_popup = page.evaluate("() => !!document.querySelector(\"[id^='anti-bot-']\")")
    print("弹窗是否出现:", has_popup)
    if has_popup:
        btn = page.query_selector("[id^='ab-btn-']")
        box = btn.bounding_box()
        print("按钮位置:", box)
        if box:
            cx = box['x'] + box['width']/2
            cy = box['y'] + box['height']/2
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.wait_for_timeout(2600)
            page.mouse.up()
            page.wait_for_timeout(1000)
            gone = page.evaluate("() => !document.querySelector(\"[id^='anti-bot-']\")")
            print("按住后弹窗是否消失:", gone)
            st = page.evaluate("() => { const v=document.querySelector('#fsplayer-container-id_html5_api'); return {paused: v?v.paused:null, ct: v?v.currentTime:null}; }")
            print("恢复播放状态:", st)
    browser.close()
