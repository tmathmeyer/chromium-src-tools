
function seek2end() {
  for (const v of document.getElementsByTagName('video')) {
    console.log('found a video element!');
    if (!v.paused) {
      console.log('v is not paused!, seeking!');
      v.currentTime = v.duration;
    } else {
      console.log('v is paused!');
    }
  }
}

chrome.action.onClicked.addListener((tab) => {
  if(!tab.url.includes("chrome://")) {
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: seek2end
    });
  }
});
