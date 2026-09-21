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
- **File conversion:** Pillow (images) + the bundled ffmpeg (audio/video) via `converter.py`
- **Stream merging:** ffmpeg — required to merge video+audio streams into mp4. Bundled into the PyInstaller build (`_internal/ffmpeg/`) so the app runs on PCs without ffmpeg; `downyt.spec` copies it from `vendor/ffmpeg/ffmpeg.exe` if present, else from PATH, and fails the build if neither exists. The binary is gitignored; `build.bat` runs `setup_ffmpeg.ps1` to download the latest gyan.dev build into `vendor/ffmpeg/` when it's missing (run it manually on a fresh clone before running from source)

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
├── queue_manager.py          # QueueManager (downloads) + ConvertManager (conversions) — threading, status tracking per item
├── converter.py              # File converter: format tables, Pillow image path, ffmpeg audio/video path with progress
├── main.py                   # Desktop entry point (pywebview window around the Flask server)
├── downyt.spec / build.bat   # PyInstaller onedir build; setup_ffmpeg.ps1 fetches ffmpeg into vendor/ffmpeg/
├── src/
│   ├── main.ts               # Frontend entry point
│   ├── queue.ts              # Queue UI logic and SocketIO event handling
│   ├── convert.ts            # Convert tab: file selection, format pickers, conversion queue UI
│   ├── types.ts              # Shared TypeScript interfaces (VideoInfo, QueueItem, etc.)
│   └── api.ts                # fetch() wrappers for Flask API routes
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js           # Vite build output (do not edit manually)
├── templates/
│   └── index.html            # Single-page UI (loads static/js/main.js)
└── downloads/                # Default output directory for finished video files
```

## Key Dependencies

**requirements.txt (Python)**
```
flask
flask-socketio
yt-dlp
pywebview
pythonnet
pillow
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
5. **Save options modal** — before adding to queue, user picks:
   - **Folder** — "Browse…" button opens the native Windows folder picker (via `tkinter.filedialog`); defaults to `downloads/`
   - **File name** — editable text field pre-filled with the video title; yt-dlp appends the correct extension automatically. Not shown for playlists (each video keeps its own title)
   - **Download subtitles** — checkbox (unchecked by default); downloads all available subtitle languages as `.srt` files alongside the video
6. **Download queue** — active downloads shown in a "Download Queue" section with a "Clear All" button
7. **Background downloading** — `queue_manager.py` runs downloads on background threads so the UI stays responsive
8. **Progress tracking** — per-item progress (%, download speed, ETA) pushed to the frontend via SocketIO
9. **Multiple simultaneous downloads** — queue supports 2 concurrent downloads (configurable via `_semaphore` in `queue_manager.py`)
10. **Audio+video merging** — video format IDs are stored as `{format_id}+bestaudio/best` so yt-dlp fetches both streams; ffmpeg merges them into a single mp4 (`merge_output_format: mp4`)
11. **Downloaded queue** — completed downloads move out of the Download Queue and into a separate "Downloaded" section automatically; has its own "Clear All" button
12. **Open folder** — each card in the Downloaded section has a folder icon button that opens Windows Explorer at the file's location (calls `/api/open-folder` → `os.startfile`)
13. **Playlist download** — user pastes a YouTube playlist URL; app fetches all video entries (title + thumbnail) and lists them; user can download the entire playlist at once or deselect individual videos before confirming; all selected videos are bulk-added to the existing download queue
14. **Subtitle download** — when enabled in the save modal, yt-dlp writes `.srt` subtitle files (`writesubtitles`, `writeautomaticsub`, `subtitlesformat: srt`); video and subtitles are placed together in a dedicated subfolder named after the video title (e.g. `downloads/My Video/My Video.mp4` + `My Video.en.srt`)
15. **Retry failed downloads** — error cards in the active queue show a "Retry Download" button (red outline); clicking it removes the failed card and re-queues the same download with identical settings (URL, format, folder, filename, subtitle preference)
16. **File converter** — the "Convert" tab converts images (png/jpg/webp/bmp/gif/tiff/ico), audio (mp3/wav/flac/m4a/ogg/opus) and video (mp4/mkv/webm/mov/gif, plus audio extraction) with per-file target format, optional output folder (default: next to the original). Progress is pushed on the `convert_update` SocketIO event. Originals are never overwritten (`name (1).ext`), and a failed conversion deletes its partial output

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Serve index.html |
| POST | `/api/fetch` | Fetch video/playlist metadata via yt-dlp |
| POST | `/api/queue` | Add one or more items to the download queue |
| GET | `/api/queue` | Get current queue state |
| POST | `/api/pick-folder` | Open native Windows folder picker (tkinter); returns `{cancelled, folder}` |
| POST | `/api/pick-files` | Native multi-file picker (tkinter); returns supported files with `kind` + valid output `formats`, and a `skipped` count |
| POST | `/api/convert` | Queue conversions: `{items: [{source, target_format, output_dir?}]}` |
| GET | `/api/convert` | Get current conversion state |
| POST | `/api/open-folder` | Open Windows Explorer at a given file path (os.startfile) |

## UI Layout & Design

### Design Language
- **Theme:** Dark — dark background (`#0f0f0f`) with slightly lighter card surfaces (`#1a1a1a` / `#242424`)
- **Accent color:** YouTube red (`#ff0000`) for primary buttons and active states; soften to `#cc0000` on hover
- **Typography:** Inter (or system-ui fallback); large weight for titles, regular for metadata, small/muted for secondary info
- **Spacing:** Generous padding inside cards (14–28px); clear vertical rhythm between sections
- **Borders & radius:** Rounded corners (`--radius: 10px`, `--radius-sm: 6px`) on cards and inputs
- **Shadows:** Soft box-shadow on the save modal card

### Page Layout Order (top → bottom)

1. **Header bar** — sticky; app logo/name ("DownYT") on the left
2. **URL input section** — centered, prominent; large input field with a "Fetch" button
3. **Error banner** — dismissible; appears below the input on bad URL or fetch failure
4. **Video preview card** — appears after a URL is fetched:
   - Thumbnail on the left (200×113px, rounded)
   - Title, channel name, duration on the right
   - Resolution picker dropdown
   - "Add to Queue" button (bottom-right of card)
5. **Playlist preview panel** — shown instead of the video card for playlist URLs:
   - "Select all" toggle at the top-right of the header
   - Scrollable list of video entries with checkbox, thumbnail, and title
   - Resolution picker + "Add Selected to Queue" button in the footer
6. **Download Queue section** — heading row with "Download Queue" label and "Clear All" button; each item is a card with thumbnail, title, status badge, progress bar, speed/ETA; failed cards show a red-outlined "Retry Download" button on the right
7. **Downloaded section** — heading row with "Downloaded" label and "Clear All" button; each completed item shows thumbnail, title, file path, full progress bar, and a folder icon button to open the file location in Explorer

### Save Options Modal

Shown when the user clicks "Add to Queue" (single video) or "Add Selected to Queue" (playlist):
- **Save to** — read-only path display + "Browse…" button (opens native folder picker); defaults to `downloads`
- **File name** — editable input pre-filled with video title (single video only; hidden for playlists)
- **Download subtitles** — checkbox (unchecked by default); label reads "Download subtitles (all available languages, .srt)"
- **Cancel / Confirm** buttons

### UI Rules
- The URL input must always be visible and accessible
- Show a loading spinner inside the preview area while metadata is being fetched
- Progress bars update smoothly in real time via SocketIO — no page reloads
- Empty queue states show a friendly placeholder message, not a blank space
- All interactive elements have clear hover and focus states
- No `alert()` or browser-native dialogs — inline error messages only
- Error messages appear as a dismissible banner below the URL input

## Coding Conventions

- Keep route handlers in `app.py` thin — business logic lives in `downloader.py` and `queue_manager.py`
- All yt-dlp interactions go through `downloader.py` only (never call yt-dlp directly from routes)
- `downloads/` directory is created automatically on startup (`os.makedirs('downloads', exist_ok=True)`)
- Do not store any user data or download history persistently — everything is in-memory per session
- Video format IDs must always be `{format_id}+bestaudio/best` for video formats (set in `_format_video`); audio-only formats use the raw format_id
- ffmpeg path is resolved in `download_video()` via `_resolve_ffmpeg_location()`, which uses the bundled copy when frozen, then `shutil.which('ffmpeg')` on PATH (dev runs); any new feature needing ffmpeg (e.g. the file converter) must use this same resolver
- On download failure, `queue_manager.py` calls `cleanup_partial_files()` in `downloader.py` to delete yt-dlp's leftover `.part`/`.ytdl` fragment files for that job; retrying a failed download therefore re-downloads from scratch rather than resuming
- Output format is always mp4 (`merge_output_format: mp4` in yt-dlp options)
- When `download_subtitles=True`, the `outtmpl` is changed to place files in a subfolder: `{output_dir}/{title}/{title}.%(ext)s`; without subtitles files go directly into `output_dir`
- `QueueItem` carries `output_dir`, `custom_filename`, and `download_subtitles` so the frontend has everything needed to retry a failed download without re-showing the save modal
- Retry button style: red outline (`.btn-retry`), error card right side only; on click it removes the failed item from `activeItems` client-side then calls `addToQueue` — the new job arrives via SocketIO like any other
- Conversions live in `converter.py` (pure functions) and `ConvertManager`; ffmpeg progress comes from `-progress pipe:1` plus the duration parsed from `ffmpeg -i`, so `ffprobe` is not needed. Run ffmpeg with `stdin=DEVNULL` and `CREATE_NO_WINDOW` (windowed app)
- Building the frontend needs Node (`npm run build`) — `static/js/main.js` is committed build output, so rebuild it after any `src/*.ts` change
