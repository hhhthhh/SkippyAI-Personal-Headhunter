chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "send_to_skippy",
    title: "⚡ Send Listing to Skippy",
    contexts: ["all"]
  });
});

async function triggerScrape(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { action: "scrape_clicked_job" });
  } catch (err) {
    // If the content script is not loaded yet (e.g. tab was open before extension install/reload),
    // inject it programmatically and retry
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ["content.js"]
      });
      await chrome.tabs.sendMessage(tabId, { action: "scrape_clicked_job" });
    } catch (injectErr) {
      console.error("Skippy: Failed to inject content script:", injectErr);
    }
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "send_to_skippy" && tab?.id) {
    triggerScrape(tab.id);
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "sendToSkippy") {
    const endpoints = [
      'http://127.0.0.1:8000/api/ingest',
      'http://localhost:8000/api/ingest'
    ];

    const tryFetch = async () => {
      let lastError = null;
      for (const url of endpoints) {
        try {
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request.payload)
          });
          if (res.ok) {
            return { success: true };
          } else {
            const errorText = await res.text().catch(() => "");
            lastError = `Server returned ${res.status}: ${errorText}`;
          }
        } catch (err) {
          lastError = err.toString();
        }
      }
      return { success: false, error: lastError || "Failed to connect to Skippy backend." };
    };

    tryFetch().then(sendResponse);
    return true; // Keep message channel open for async response
  }
});
