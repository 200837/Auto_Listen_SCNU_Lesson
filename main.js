$(document).ready(function () {
  function getCurrentTimeStamp() {
    return new Date().getTime();
  }
  // 新增：检测不兼容浏览器并弹窗提醒（iOS 夸克 / Android 百度）
  function isIOSQuark() {
    var ua = (navigator.userAgent || "").toLowerCase();
    return /quark/.test(ua) && /iphone|ipad|ipod/.test(ua);
  }
  function isAndroidBaidu() {
    var ua = (navigator.userAgent || "").toLowerCase();
    // 包含 baidubox、baiduboxapp、baidubrowser 等可能的百度内核标识，并且是 Android 平台
    return (
      /baidubox|baiduboxapp|baidubrowser|baidubox\/|;bd/.test(ua) &&
      /android/.test(ua)
    );
  }
  // console.log("playerdata", playerdata);
  var sourceData =
  playerdata && playerdata.source ? JSON.parse(playerdata.source) : {};
  var sources = {};

  // 流畅
  if(sourceData?.FD) {
    sources.FD = [{
        src: sourceData.FD
    }];
  }
  // 标清
  if(sourceData?.LD) {
    sources.LD = [{
        src: sourceData.LD
    }];
  }
  // 标高清
  if(sourceData?.SD) {
    sources.SD = [{
        src: sourceData.SD
    }];
    defaultRes = 'SD';
  }
  // 高清
  if(sourceData?.HD) {
    sources.HD = [{
        src: sourceData.HD
    }];
  }
  // 超清
  if(sourceData?.OD) {
    sources.FHD = [{
        src: sourceData.OD
    }];
  }
  var $containerWrapper = $("#player-con");
  var videoId = "fsplayer-container-id"; // 替换为你的视频 ID
  let $tcplayerContainer = $(videoId);
  if (isIOSQuark() || isAndroidBaidu()) {
    alert(
      " 经检测，您当前使用的浏览器与系统某些功能可能不兼容。建议使用小程序或企业微信进行学习以获得更稳定的体验。"
    );
  }
  // 如果视频容器不存在，直接新建video容器
  if (!$tcplayerContainer.length) {
    $tcplayerContainer = $(
      `<video id="${videoId}" webkit-playsinline="true" playsinline="true" preload="auto" width="100%" height="100%"></video>`
    ).appendTo($containerWrapper);
  }
  // const videoUrl = source['1'] || source['0'] || source['4']; // 0源码，1低码，4高码
  var serverUploadUrl =
    playerdata.siteUrl +
    "/lib/ajax/service.php?timestamp=" +
    getCurrentTimeStamp() +
    "&sesskey=" +
    playerdata.sesskey; // 替换为你的服务器上传 URL
  var localStorageKey = `fs_${playerdata.userid}_${
    playerdata.fsresourceid || 0
  }`; // 用于本地存储的键
  var playerWrapper = new TCPlayerWrapper(
    videoId,
    sources,
    serverUploadUrl,
    localStorageKey,
    15 * 1000,
    playerdata.progress == 1
  );
  // 在页面卸载时保存播放进度（可选，因为用户可能直接关闭浏览器标签）
  $(window).on("beforeunload", () => {
    playerWrapper.saveTime();
  });
});
