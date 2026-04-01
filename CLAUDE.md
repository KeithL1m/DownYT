# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DownYT — a YouTube downloader web app. Users paste a YouTube link, see the video thumbnail and title to verify it's the right video, pick a resolution, then add it to a download queue. Multiple videos can be queued and downloaded simultaneously.

## Tech Stack

- **Backend:** Python + Flask
- **YouTube engine:** yt-dlp (handles metadata, thumbnail URLs, resolution listing, and downloading)
- **Frontend:** TypeScript (vanilla — no React/Vue) compiled via Vite
- **Real-time updates:** Flask-SocketIO (backend) + socket.io-client (frontend TypeScript package)
- **Build tool:** Vite — compiles `src/*.ts` → `static/js/`, no framework required

## File Structure

```
DownYT/
├── CLAUDE.md
├── requirements.txt          # Python dependencies
├── package.json              # Node dependencies (Vite, TypeScript, socket.io-client)
├── tsconfig.json             # TypeScript compiler config
├── vite.config.ts            # Vite build config (output → static/js/)
├── app.py                    # Flask entry point — routes and SocketIO events
├── downloader.py             # yt-dlp wrapper: fetch_info(), start_download()
├── queue_manager.py          # Queue logic — threading, status tracking per item
├── src/
│   ├── main.ts               # Frontend entry point
│   ├── queue.ts              # Queue UI logic and SocketIO event handling
│   ├── types.ts              # Shared TypeScript interfaces (VideoInfo, QueueItem, etc.)
│   └── api.ts                # fetch() wrappers for Flask API routes
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js           # Vite build output (do not edit manually)
├── templates/
│   └── index.html            # Single-page UI (loads static/js/main.js)
└── downloads/                # Output directory for finished video files
```

## Key Dependencies

**requirements.txt (Python)**
```
flask
flask-socketio
yt-dlp
```

**package.json (Node)**
```
vite
typescript
socket.io-client
```

## App Features / Capabilities

1. **URL input** — user pastes any YouTube link (single video or playlist)
2. **Metadata fetch** — calls yt-dlp to get title, thumbnail URL, and list of available resolutions
3. **Thumbnail preview** — displays the video thumbnail and title so user can confirm the correct video
4. **Resolution picker** — dropdown of available formats (e.g. 1080p, 720p, 480p, 360p, audio-only)
5. **Download queue** — each confirmed download is added to a queue list
6. **Background downloading** — queue_manager.py runs downloads on background threads so the UI stays responsive
7. **Progress tracking** — per-item progress (%, download speed, ETA) pushed to the frontend via SocketIO
8. **Multiple simultaneous downloads** — queue supports N concurrent downloads (configurable)
9. **Playlist download** — user pastes a YouTube playlist URL; app fetches all video entries (title + thumbnail) and lists them; user can download the entire playlist at once or deselect individual videos before confirming; all selected videos are bulk-added to the existing download queue

## UI Layout & Design

### Design Language
- **Theme:** Dark — dark background (`#0f0f0f` or `#111111`) with slightly lighter card surfaces (`#1e1e1e`)
- **Accent color:** YouTube red (`#ff0000`) for primary buttons and active states; soften to `#cc0000` on hover
- **Typography:** Clean sans-serif (Inter or system-ui); large weight for titles, regular for metadata, small/muted for secondary info like file size and ETA
- **Spacing:** Generous padding inside cards (16–24px); clear vertical rhythm between sections — no cramped or cluttered areas
- **Borders & radius:** Subtle rounded corners (8–12px) on cards and inputs; no harsh square edges
- **Shadows:** Soft box-shadows on cards to lift them off the background

### Page Layout Order (top → bottom)

1. **Header bar** — app logo/name ("DownYT") on the left; minimal, no clutter
2. **URL input section** — centered, prominent; large input field with a "Fetch" button; this is the primary action and should feel like the hero of the page
3. **Video preview card** — appears below the input after a URL is fetched:
   - Thumbnail on the left (fixed width, rounded corners)
   - Video title, channel name, and duration on the right
   - Resolution picker dropdown below the metadata
   - "Add to Queue" button aligned to the bottom-right of the card
4. **Playlist preview panel** — shown instead of the single video card when a playlist URL is detected:
   - "Select All / Deselect All" toggle at the top
   - Scrollable grid or list of video entries, each with thumbnail, title, and a checkbox
   - "Add Selected to Queue" button fixed at the bottom of the panel
5. **Download queue section** — below the preview area; always visible once at least one item is queued:
   - Each queue item is a card row: thumbnail (small) → title → status badge → progress bar → speed/ETA
   - Completed items show a green checkmark and the output file name
   - Failed items show a red error badge with a retry button

### UI Rules
- The URL input must always be visible and accessible — do not hide or collapse it
- Show a loading spinner inside the video preview card area while metadata is being fetched
- Progress bars must update smoothly in real time via SocketIO — no page reloads
- Empty queue state should show a friendly placeholder message, not a blank space
- All interactive elements (buttons, dropdowns, checkboxes) must have clear hover and focus states
- Do not use alert() or browser-native dialogs — use inline error messages styled within the UI
- Error messages (bad URL, fetch failed, download failed) appear as a dismissible banner below the URL input

## Coding Conventions

- Keep route handlers in `app.py` thin — business logic lives in `downloader.py` and `queue_manager.py`
- All yt-dlp interactions go through `downloader.py` only (never call yt-dlp directly from routes)
- `downloads/` directory should be created automatically on startup if it does not exist
- Do not store any user data or download history persistently — everything is in-memory per session
