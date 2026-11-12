
// script.js
class TCPlayerWrapper {
  constructor(videoId, sources, serverUploadUrl, localStorageKey, taskUpdateTime = 10 * 1000, progressControl = true) {
    this.task = null
    this.timer = null;
    this.videoId = videoId;
    this.sources = sources;
    this.licenseUrl = "https://license.vod2.myqcloud.com/license/v2/1315542118_1/v_cube.license"
    this.serverUploadUrl = serverUploadUrl;
    this.localStorageKey = localStorageKey;
    this.player = null;
    this.lastPlayedTime = 0;
    this.intervalId = null;
    this.taskUpdateTime = taskUpdateTime // 定时器请求后台的时间，默认30秒请求一次
    this.showMessage = false
    this.progressControl = progressControl
    this.viewTotalTime = 0; // 浏览视频时长，只有视频正常播放的时候才累加，视频缓冲中或者暂停时应该停止累加
    this.videoDuration = 0 // 视频总时长
    this.playerState = 0 // 0未开始 1播放中 2暂停 3结束
    // 生成当前页面唯一ID
    this.pageId = `${Date.now()}_${Math.random()}`;
    this.initPlayer();
    // --- anti-bot state ---
    this.antiBot = {
      challengeOpen: false, // 当前是否正在显示人机验证弹窗
      requiresChallenge: false, // 当前视频是否需要人机验证
      challengeIntervalMs: 0, // 验证间隔（毫秒）
      challengePassUntil: 0, // 在该时间戳前允许累计观看时长
      nextChallengeAt: 0, // 下一次需要弹窗验证的时间戳
    };
  }
  // 初始化播放器
  initPlayer() {
    const templist = [
      {
        label: '流畅',
        value: 'FD'
      },
      {
        label: '标清',
        value: 'LD'
      },
      {
        label: '标高清',
        value: 'SD'
      },
      {
        label: '高清',
        value: 'HD'
      },
      {
        label: '超清',
        value: 'FHD'
      },
    ]
    let labels = {}
    const showOrder = []
    let defaultRes = ''
    for(let i=0;i<templist.length;i++) {
      if(this.sources[templist[i].value]) {
        labels[templist[i].value] = templist[i].label
        showOrder.push(templist[i].value)
        if(!defaultRes) {
          defaultRes = templist[i].value
        }
      }
    }
    this.player = TCPlayer(this.videoId, {
      licenseUrl: this.licenseUrl, // license 地址，参考准备工作部分，在视立方控制台申请 license 后可获得 licenseUrl
      language: 'zh-CN',
      playbackRates: [], // 为空则隐藏倍率
      multiResolution: {
        sources: this.sources,
        // 配置每个清晰度标签
        labels,
        // 配置各清晰度在播放器组件上的顺序
        showOrder,
        // 配置默认选中的清晰度
        defaultRes,
      },
      controlBar: {
        progressControl: this.progressControl
      }
    })
    this.player.on("ready", (e) => {
      // console.log('ready player', this.player);
      this.restorePlaybackPosition();
      this.setupEventListeners();
    });
  }
  // 设置事件监听
  setupEventListeners() {
    this.player.on('play', (e) => {
      // console.log('play', this.player.duration());
      // 部分播放器在 play 初期还拿不到 duration，这里做一次安全读取。
      if (!this.videoDuration) {
        const duration = this.player.duration();
        if (Number.isFinite(duration) && duration > 0) {
          this.videoDuration = duration;
        }
      }
      // 根据总时长计算“是否需要验证”和“验证间隔”。
      this.updateChallengePolicyByDuration();
      this.timer === null && this.setTimerInterval()
      this.task === null && this.setTaskInterval()
    });
    this.player.on('timeupdate', (e) => {
      // 时长可能在播放后才就绪，timeupdate 中兜底重取并更新策略。
      if (!this.videoDuration) {
        const duration = this.player.duration();
        if (Number.isFinite(duration) && duration > 0) {
          this.videoDuration = duration;
          this.updateChallengePolicyByDuration();
        }
      }
      this.playerState = 1
      this.lastPlayedTime = this.player.currentTime();
    });

    this.player.on('pause', (e) => {
      this.playerState = 2
      // 可以在这里添加额外的暂停逻辑
      this.showMessage === false && this.ajaxOrder();
      // console.log('pause');
    });

    this.player.on('ended', (e) => {
      this.playerState = 3
      // console.log('ended');
      this.clearTimerInterval();
      this.clearTaskInterval()
    });
  }
  // 恢复播放进度
  restorePlaybackPosition() {
    const savedTime = this.getTime();
    // console.log('savedTime', savedTime);
    if (savedTime) {
      this.player.currentTime(parseFloat(savedTime));
    }
  }
  // 定时上传播放进度
  ajaxOrder() {
    // 这里实现上传逻辑，例如通过 AJAX 请求发送到服务器
    // 误差情况分析：1 网络请求失败引起的误差，比较严重，因为每次请求后都会马上清空viewTotalTime,
    // 故如果视频仍在播放中，缺少的时间为：失败的次数*viewTotalTime
    // 解决方法是在ajax失败的时候把请求的time累加到当前时间
    //浏览时长为小于等于0时不上传
    if (this.viewTotalTime <= 0) return
    var nowpoint = Math.floor(this.player.currentTime() * 1000)
    var videoTotalDuration = this.videoDuration * 1000
    var finish = 0;
    var progress = 0;
    // console.log('nowpoint', nowpoint);
    // console.log('videoDuration', videoTotalDuration);
    // 当前时间大于等于总时间，说明已经播放完成,这里多加250毫秒是为了避免播放到最后一秒时，视频结束了，进度没有为100%
    if (nowpoint + 250 >= videoTotalDuration) {
      finish = 1;
      progress = 100;
    } else if (nowpoint < videoTotalDuration) {
      progress = Number((nowpoint / videoTotalDuration) * 100).toFixed(2);
    }
    var data = Array();
    var time = Math.round(this.viewTotalTime / 1000)

    data[0] = {
      'index': 0,
      'methodname': 'mod_fsresource_set_time',
      'args': {
        'fsresourceid': playerdata.fsresourceid,
        'time': time, // 浏览视频时长
        'finish': finish, // 是否是否结束
        'progress': progress, // 当前播放进度
        'unique': this.pageId, // 当前页面唯一ID
      },
    };
    // console.log('finish--', finish, '::progress--', progress, '::time--', time);
    $.ajax({
      url: this.serverUploadUrl,
      method: 'POST',
      data: JSON.stringify(data),
      success: (response)=> {
        // 请求失败，把请求失败的时长累加到当前浏览时长
        if (response[0] && response[0].data) {
          if (response[0].data.status) {
            this.showMessage = false
            this.updateTableData(response[0].data)
            if (response[0].data.warnings[0] &&response[0].data.warnings[0].warningcode == 'tostop') {
              this.insertAlertToBody(response[0].data.warnings[0].message)
            }
          } else {
            this.showMessage = false
            this.player.pause()
            alert(response[0].data.warnings[0].message)
          }
        } else {
          this.viewTotalTime += data[0].args.time * 1000
          this.showMessage = true
          this.player.pause()
          alert('更新进度失败：' + response[0] && response[0].exception ? response[0].exception : '请检查网络是否异常')
        }
      },
      error: (xhr, status, error) => {
        // 请求失败，把请求失败的时长累加到当前浏览时长
        this.viewTotalTime += data[0].args.time * 1000
        // console.log('请求失败', this.viewTotalTime);
        this.showMessage = true
        this.player.pause()
        alert('网络异常，请检查网络并刷新网页重新加载尝试')
      }
    })
    this.viewTotalTime = 0;
  }
  // 更新页面观看时长信息
  updateTableData(data) {
    $('.num-bfjd span').html(data['progress']);
    $('.num-gksc span').html(data['totaltime']);
    $('.tips span.tips-completion').html(data['completion']);
  }
  //同时播放提示
  insertAlertToBody(message) {
    var alertHtml = `
    <div class="alert alert-warning alert-block fade in alert-dismissible" role="alert" data-aria-autofocus="true">
      ${message}
        <button type="button" class="close" data-dismiss="alert">
          <span aria-hidden="true">&times;</span>
        </button>
    </div>`
    $('#user-notifications').append(alertHtml);
  }
  // 保存播放进度，一般页面卸载时本地保存
  saveTime() {
    localStorage.setItem(this.localStorageKey, this.lastPlayedTime);
  }
  getTime() {
    //return返回的是自定义起播时间
    return localStorage.getItem(this.localStorageKey)
  }
  // 设置浏览时长定时器
  setTimerInterval() {
    if (this.timer) this.clearTimerInterval()
    this.timer = setInterval(() => {
      // console.log('playerState', this.playerState);
      if (this.playerState == 1) {
        const t = this.now();
        // 仅当该视频需要验证且达到触发时间时弹窗。
        const needChallenge = this.antiBot.requiresChallenge && t >= this.antiBot.nextChallengeAt;
        if (needChallenge && !this.antiBot.challengeOpen) {
          this.openHumanChallenge();
        }

        // 只有在“验证通过窗口期”内才累计观看时长。
        if (this.isChallengePassed()) {
          this.viewTotalTime += 250;
        }
      }
      this.saveTime()
    }, 250)
  }
  // 设置请求后台定时器
  setTaskInterval() {
    if (this.task) this.clearTaskInterval()
    this.task = setInterval(() => {
      this.ajaxOrder();
    }, this.taskUpdateTime)
    setTimeout(() => {
        this.ajaxOrder();
    }, 1000)
  }
  // 清除求后台定时器
  clearTaskInterval() {
    clearInterval(this.task);
    this.task = null;
  }
  // 清除浏览时长定时器
  clearTimerInterval() {
    clearInterval(this.timer);
    this.timer = null;
  }
  randMs(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }
  
  now() {
    return Date.now();
  }
  
  isChallengePassed() {
    // 不需要验证的短视频，默认允许累计。
    if (!this.antiBot.requiresChallenge) return true;
    // 需要验证时，只在通过后的有效窗口内允许累计。
    return this.now() < this.antiBot.challengePassUntil;
  }

  updateChallengePolicyByDuration() {
    const durationMs = this.videoDuration * 1000;
    const tenMinutesMs = 10 * 60 * 1000; // 10分钟
    const fifteenMinutesMs = 30 * 60 * 1000; // 15分钟
    const twentyMinutesMs = 20 * 60 * 1000; // 20分钟
    const thirtyMinutesMs = 30 * 60 * 1000; // 30分钟

    // 时长未就绪时先不下结论，避免误判为“不需要验证”.
    if (!Number.isFinite(durationMs) || durationMs <= 0) {
      return;
    }

    if (durationMs <= tenMinutesMs) {
      // 不超过10分钟：不弹窗验证，始终允许累计。
      this.antiBot.requiresChallenge = false;
      this.antiBot.challengeIntervalMs = 0;
      this.antiBot.challengePassUntil = Number.MAX_SAFE_INTEGER;
      this.antiBot.nextChallengeAt = Number.MAX_SAFE_INTEGER;
      return;
    }

    // 超过10分钟：开启人机验证。
    this.antiBot.requiresChallenge = true;
    // 10~15分钟每10分钟验证一次
    if(durationMs <= fifteenMinutesMs) {
      this.antiBot.challengeIntervalMs = tenMinutesMs;
    } else {
      // 10~30分钟每15分钟验证一次，超过30分钟每20分钟验证一次。
      this.antiBot.challengeIntervalMs = durationMs <= thirtyMinutesMs ? fifteenMinutesMs : twentyMinutesMs;
    }
    
    if (!this.antiBot.nextChallengeAt || this.antiBot.nextChallengeAt === Number.MAX_SAFE_INTEGER) {
      // 首次触发时间：从“当前时刻 + 验证间隔”开始，不在首次播放立即弹窗。
      const firstChallengeAt = this.now() + this.antiBot.challengeIntervalMs;
      this.antiBot.nextChallengeAt = firstChallengeAt;
      // 首次触发前允许正常累计；到点后会暂停并要求验证。
      this.antiBot.challengePassUntil = firstChallengeAt;
    }
  }
  openHumanChallenge() {
    if (this.antiBot.challengeOpen) return;
    this.antiBot.challengeOpen = true;
  
    // 暂停播放，防止脚本无感通过
    try { this.player.pause(); } catch (_) {}
  
    const nonce = Math.random().toString(36).slice(2, 8);
    const holdMs = this.randMs(1200, 2200);
    const btnText = `按住通过`;
    const mask = document.createElement('div');
    mask.id = `anti-bot-${nonce}`;
    mask.style.cssText = `
      position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:999999;
      display:flex;align-items:center;justify-content:center;
    `;
  
    const panel = document.createElement('div');
    panel.style.cssText = `
      width:360px;max-width:92vw;background:#fff;border-radius:10px;
      padding:18px;box-shadow:0 8px 30px rgba(0,0,0,.25);font-size:14px;color:#222;
    `;
    panel.innerHTML = `
      <div style="font-weight:600;margin-bottom:8px;">学习确认</div>
      <div style="margin-bottom:12px;line-height:1.6;">
        请按住按钮直到进度条满，确认你在观看
      </div>
      <div style="height:8px;background:#eee;border-radius:8px;overflow:hidden;margin-bottom:10px;">
        <div id="ab-bar-${nonce}" style="height:100%;width:0;background:#1677ff;"></div>
      </div>
      <button id="ab-btn-${nonce}" style="width:100%;height:36px;border:0;border-radius:8px;background:#1677ff;color:#fff;cursor:pointer;">
        ${btnText}
      </button>
    `;
    mask.appendChild(panel);
    document.body.appendChild(mask);
  
    const btn = panel.querySelector(`#ab-btn-${nonce}`);
    const bar = panel.querySelector(`#ab-bar-${nonce}`);
  
    let downAt = 0;
    let rafId = 0;
    const start = () => {
      downAt = this.now();
      const step = () => {
        const elapsed = this.now() - downAt;
        const p = Math.min(100, (elapsed / holdMs) * 100);
        bar.style.width = `${p}%`;
        if (elapsed >= holdMs) {
          cleanup(true);
          return;
        }
        rafId = requestAnimationFrame(step);
      };
      rafId = requestAnimationFrame(step);
    };
    const stop = () => {
      cancelAnimationFrame(rafId);
      bar.style.width = '0%';
      downAt = 0;
    };
  
    const cleanup = (pass) => {
      cancelAnimationFrame(rafId);
      btn.removeEventListener('pointerdown', start);
      window.removeEventListener('pointerup', stop);
      mask.remove();
      this.antiBot.challengeOpen = false;
  
      if (pass) {
        // 验证通过后，放行到下一次触发点。
        const nextChallengeAt = this.now() + this.antiBot.challengeIntervalMs;
        this.antiBot.nextChallengeAt = nextChallengeAt;
        this.antiBot.challengePassUntil = nextChallengeAt;
        try { this.player.play(); } catch (_) {}
      }
    };
  
    btn.addEventListener('pointerdown', start);
    window.addEventListener('pointerup', stop);
  }
}
