import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import urllib.request

urls = {
    "tcplayer-video.js": "https://moodle.scnu.edu.cn/mod/fsresource/javascript/tcplayer/tcplayer-video.js",
    "main.js": "https://moodle.scnu.edu.cn/mod/fsresource/javascript/tcplayer/main.js",
}
for name, u in urls.items():
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(name, "wb") as f:
        f.write(data)
    print(name, len(data), "bytes saved")
