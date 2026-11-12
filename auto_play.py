#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
砺儒云课堂(moodle.scnu.edu.cn) 自动刷网课程序 —— 真实播放模式
原理：打开视频页 → 点击播放 → 从头真实播放到结束，靠播放器自身(TCPlayer)
每15秒自动 POST mod_fsresource_set_time 上报进度；播放到结尾时播放器自动上报
finish=1/progress=100，视频即标记"已完成"。
不直接伪造 POST、不 seek、不加速、不倍速，完全模拟真人观看。
"""

import io, sys, os, re, json, time, getpass
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "https://moodle.scnu.edu.cn"
STATE_FILE = "completed.json"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ---------------------------------------------------------------- 登录 ----
def sso_login(page, user, pwd):
    """统一身份认证(SSO)登录，返回是否成功"""
    page.goto(f"{BASE}/login/index.php", wait_until="domcontentloaded", timeout=60000)
    # 跳转到 SSO
    try:
        page.click("a[href*='sso.scnu.edu.cn']", timeout=15000)
    except PWTimeout:
        pass
    page.wait_for_load_state("domcontentloaded")
    for _ in range(30):
        if 'sso.scnu.edu.cn' in page.url and 'login.html' in page.url:
            break
        page.wait_for_timeout(500)
    # 填账号密码并提交
    page.fill("#account", user)
    page.fill("#password", pwd)
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('#login-form-password').submit()")
    page.wait_for_load_state("domcontentloaded")
    for _ in range(40):
        if 'moodle.scnu.edu.cn' in page.url:
            break
        page.wait_for_timeout(500)
    # 确认登录页（"确定登录"按钮）
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
    return 'moodle.scnu.edu.cn' in page.url and '/login/' not in page.url

def ensure_login(page, user, pwd):
    """确保处于登录态；失效则重登"""
    if 'MoodleSession' not in [c['name'] for c in page.context.cookies()]:
        return sso_login(page, user, pwd)
    return True

# ------------------------------------------------------------ 课程/视频列表 ----
def list_courses(page):
    """从我的主页抓课程列表，返回 [(course_id, course_name)]"""
    page.goto(f"{BASE}/my/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    data = page.evaluate("""() => {
        const seen = new Set(); const out = [];
        document.querySelectorAll("a[href*='course/view.php?id=']").forEach(a => {
            const m = a.href.match(/id=(\\d+)/); if (!m) return;
            const id = m[1];
            if (seen.has(id)) return; seen.add(id);
            const name = (a.textContent || '').trim();
            if (name) out.push({id, name});
        });
        return out;
    }""")
    return [(c['id'], c['name']) for c in data]

def list_videos(page, course_id):
    """抓课程内所有视频及完成状态，返回 (完成列表, 未完成列表)，每项 (cmid, name)"""
    page.goto(f"{BASE}/course/view.php?id={course_id}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    videos = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('li.courseindex-item').forEach(li => {
            const a = li.querySelector('a.courseindex-link[href*="mod/fsresource/view.php?id="]');
            if (!a) return;
            const m = a.href.match(/id=(\\d+)/); if (!m) return;
            const ci = li.querySelector('.completioninfo');
            const dv = ci ? ci.getAttribute('data-value') : null;
            out.push({id: m[1], name: (a.textContent||'').trim(), dv});
        });
        return out;
    }""")
    complete = [(v['id'], v['name']) for v in videos if v['dv'] == '1']
    incomplete = [(v['id'], v['name']) for v in videos if v['dv'] == '0']
    return complete, incomplete

# ------------------------------------------------------------ 播放核心 ----
def handle_challenge(page):
    """处理"学习确认"弹窗：按住按钮直到进度条满"""
    btn = page.query_selector("[id^='ab-btn-']")
    if not btn:
        return False
    try:
        box = btn.bounding_box()
        if box:
            cx = box['x'] + box['width'] / 2
            cy = box['y'] + box['height'] / 2
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.wait_for_timeout(2600)  # holdMs 最大 2200ms，留余量
            page.mouse.up()
            log("  已通过「学习确认」弹窗")
    except Exception as e:
        log(f"  弹窗处理异常: {e}")
    page.wait_for_timeout(500)
    return True

def play_video(page, cmid, name):
    """真实播放一个视频直到完成，返回是否成功标记完成"""
    url = f"{BASE}/mod/fsresource/view.php?id={cmid}"
    log(f"▶ 开始播放: {name} (cmid={cmid})")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)  # 等播放器 ready

    finished = {"done": False}
    def on_request(req):
        if 'mod_fsresource_set_time' in req.url:
            try:
                body = req.post_data or ""
                if '"finish":1' in body or '"finish": 1' in body:
                    finished["done"] = True
                    log("  ✔ 收到播放器 finish=1 上报，视频已完成")
            except Exception:
                pass
    page.on("request", on_request)

    # 点击播放
    try:
        page.click(".vjs-big-play-button", timeout=8000)
    except PWTimeout:
        page.evaluate("() => { const v=document.querySelector('#fsplayer-container-id_html5_api'); if(v){ v.muted=true; v.play(); } }")

    # 播放循环
    last_ct = -1
    stall_count = 0
    last_log = 0
    while not finished["done"]:
        # 1) 处理学习确认弹窗
        if page.query_selector("[id^='anti-bot-']"):
            handle_challenge(page)
            continue
        # 2) 读取播放状态
        st = page.evaluate("""() => {
            const v = document.querySelector('#fsplayer-container-id_html5_api');
            return {paused: v ? v.paused : true, ended: v ? v.ended : false,
                    ct: v ? v.currentTime : 0, dur: v ? v.duration : 0};
        }""")
        ct, dur = st['ct'], st['dur']
        # 3) 意外暂停（非弹窗、非结束）→ 恢复播放
        if st['paused'] and not st['ended'] and not (dur > 0 and ct >= dur - 1):
            page.evaluate("() => { const v=document.querySelector('#fsplayer-container-id_html5_api'); if(v) v.play(); }")
        # 4) 播放到结尾 → 触发 pause 让播放器自然上报 finish=1
        if st['ended'] or (st['paused'] and dur > 0 and ct >= dur - 1):
            page.evaluate("() => { const v=document.querySelector('#fsplayer-container-id_html5_api'); if(v) v.pause(); }")
            page.wait_for_timeout(4000)
            if finished["done"]:
                break
            prog = page.evaluate("() => { const e=document.querySelector('.num-bfjd span'); return e?e.textContent:''; }")
            try:
                if prog and float(prog) >= 100:
                    finished["done"] = True
                    log("  ✔ 页面进度已达 100%")
                    break
            except ValueError:
                pass
        # 5) 卡顿检测：currentTime 长时间不动且未暂停
        if ct == last_ct and not st['paused']:
            stall_count += 1
        else:
            stall_count = 0
        last_ct = ct
        # 每60秒打印一次播放进度
        if time.time() - last_log >= 60:
            last_log = time.time()
            if dur > 0:
                log(f"  播放中 {ct:.0f}s/{dur:.0f}s ({ct/dur*100:.1f}%)")
        if stall_count >= 60:  # 约2分钟不动 → 刷新页面重试
            log("  ⚠ 检测到长时间卡顿，刷新页面重试")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            try:
                page.click(".vjs-big-play-button", timeout=8000)
            except PWTimeout:
                page.evaluate("() => { const v=document.querySelector('#fsplayer-container-id_html5_api'); if(v){ v.muted=true; v.play(); } }")
            stall_count = 0
            continue
        page.wait_for_timeout(2000)

    log(f"✔ 完成: {name}")
    return finished["done"]

# ------------------------------------------------------------ 主流程 ----
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", help="学号/账号")
    ap.add_argument("--pwd", help="密码")
    ap.add_argument("--course", help="课程id(可选，跳过课程选择)")
    args = ap.parse_args()

    user = args.user or input("请输入学号/账号: ").strip()
    pwd = args.pwd or getpass.getpass("请输入密码: ")

    # 已完成的视频（断点续传）
    done_ids = set()
    if os.path.exists(STATE_FILE):
        try:
            done_ids = set(json.load(open(STATE_FILE, encoding='utf-8')))
        except Exception:
            done_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        if not sso_login(page, user, pwd):
            log("✖ 登录失败，请检查账号密码")
            browser.close()
            return

        # 选择课程
        course_id = args.course
        if not course_id:
            courses = list_courses(page)
            print("\n可选课程:")
            for i, (cid, cname) in enumerate(courses, 1):
                print(f"  {i}. [{cid}] {cname}")
            choice = input("请输入要刷的课程序号: ").strip()
            try:
                course_id = courses[int(choice) - 1][0]
            except (ValueError, IndexError):
                log("✖ 序号无效")
                browser.close()
                return

        complete, incomplete = list_videos(page, course_id)
        print(f"\n课程[{course_id}] 视频统计: 总数 {len(complete)+len(incomplete)}，"
              f"已完成 {len(complete)}，未完成 {len(incomplete)}")

        # 过滤掉已断点完成的
        todo = [(cid, name) for cid, name in incomplete if cid not in done_ids]
        print(f"本次待刷: {len(todo)} 个视频\n")

        if not todo:
            print("没有需要刷的视频。")
            browser.close()
            return

        for i, (cid, name) in enumerate(todo, 1):
            log(f"[{i}/{len(todo)}] {name}")
            try:
                ok = play_video(page, cid, name)
                if ok:
                    done_ids.add(cid)
                    json.dump(sorted(done_ids), open(STATE_FILE, 'w', encoding='utf-8'))
                else:
                    log(f"  ⚠ 未能确认完成，跳过: {name}")
            except Exception as e:
                log(f"  ✖ 播放异常，跳过: {name} ({e})")
            page.wait_for_timeout(1500)

        log(f"全部处理完毕，本次完成 {len(done_ids)} 个视频")
        browser.close()

if __name__ == "__main__":
    main()
