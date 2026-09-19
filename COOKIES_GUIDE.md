# YouTube Cookies & VPS Deployment Guide

Toolyt uses an advanced yt-dlp engine with **Android and iOS mobile player clients** configured by default, which bypasses YouTube's web bot detection ("Sign in to confirm you're not a bot") on most VPS/datacenter IP addresses without requiring authentication.

However, for 100% production reliability (e.g., for age-restricted videos, high-volume server traffic, or strict datacenter IP ranges), you can configure YouTube cookies.

---

## Method 1: Drop `cookies.txt` in the Root Folder (Recommended)

1. Install a browser extension on your personal computer:
   - **Chrome / Brave / Edge**: [Get cookies.txt locally](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - **Firefox**: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Log in to your personal or burner YouTube/Google account in your browser.
3. Open YouTube (`https://www.youtube.com`).
4. Click the extension icon and export/download your cookies in **Netscape HTTP Cookie format** as `cookies.txt`.
5. Upload or copy this `cookies.txt` file directly into the Toolyt project folder on your VPS:
   ```bash
   scp cookies.txt user@your-vps-ip:/path/to/Toolyt/cookies.txt
   ```
6. Toolyt will **automatically detect and use** `cookies.txt` immediately with zero server restarts required!

---

## Method 2: Set Environment Variable in `.env`

If you are using Docker or environment files, you can configure cookies in your `.env`:

### Option A: Specific File Path
```bash
YOUTUBE_COOKIES_PATH=/path/to/cookies.txt
```

### Option B: Paste Cookies Content Directly in `.env`
You can paste the text content of your `cookies.txt` directly into the `.env` variable:
```bash
YOUTUBE_COOKIES_CONTENT="# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
.youtube.com	TRUE	/	TRUE	1750000000	LOGIN_INFO	...
"
```

---

## Method 3: Use a Proxy (Optional)

If your VPS IP is globally rate-limited or blocked by YouTube:
```bash
YOUTUBE_PROXY=http://username:password@proxyserver.com:8080
```
Or standard system proxies:
```bash
HTTP_PROXY=http://proxyserver:port
HTTPS_PROXY=http://proxyserver:port
```

---

## Direct File Upload (Zero-Restriction Fallback)

Toolyt now includes a **Direct Video File Upload** tab on the homepage. If YouTube ever temporarily blocks an IP, creators can simply upload their video file (.mp4, .mov, .mkv, .webm) directly from their computer or mobile phone. It converts into 9:16 Shorts with zero third-party platform restrictions!
