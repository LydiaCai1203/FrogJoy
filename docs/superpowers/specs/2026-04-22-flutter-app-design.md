# BookReader Flutter App Design

## Overview

Flutter mobile app (Android + iOS) for BookReader, full-feature replication of the existing React web client. Shares the same FastAPI backend and all API endpoints.

## Tech Stack

- **Framework**: Flutter (Android + iOS)
- **State Management**: Riverpod
- **Routing**: GoRouter
- **HTTP**: Dio
- **EPUB Rendering**: WebView (webview_flutter)
- **Audio**: just_audio
- **Local Storage**: Hive + flutter_secure_storage
- **Key Packages**: flutter_riverpod, go_router, dio, webview_flutter, just_audio, hive_flutter, flutter_secure_storage

## Project Structure

```
book_reader_app/
├── lib/
│   ├── main.dart
│   ├── app.dart                     # MaterialApp + GoRouter + Theme
│   ├── core/
│   │   ├── theme/                   # 4 themes: day/night/eye-care/fresh-green
│   │   ├── network/                 # Dio config, interceptors, token management
│   │   ├── storage/                 # Hive + SharedPreferences
│   │   └── constants.dart
│   ├── features/
│   │   ├── auth/
│   │   │   ├── data/               # AuthRepository, AuthApi
│   │   │   ├── domain/             # User model, AuthState
│   │   │   └── presentation/       # LoginPage, RegisterPage
│   │   ├── bookshelf/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   └── presentation/       # BookshelfPage, BookCard, UploadSheet
│   │   ├── reader/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   └── presentation/       # ReaderPage, ReaderWebView, ToolBar, ChapterDrawer
│   │   ├── tts/
│   │   │   ├── data/               # TTSRepository, AudioCache
│   │   │   ├── domain/             # TTSState, Voice, WordTimestamp
│   │   │   └── presentation/       # FloatingPlayButton, TTSControlPanel
│   │   ├── highlight/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   └── presentation/       # HighlightMenu, NoteEditor
│   │   ├── translation/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   └── presentation/
│   │   └── profile/
│   │       ├── data/
│   │       ├── domain/
│   │       └── presentation/       # ProfilePage, ReadingStats, SettingsPage
│   ├── providers/                   # Global Riverpod providers
│   └── shared/                      # Reusable widgets
├── assets/
├── android/
├── ios/
└── pubspec.yaml
```

Each feature follows data / domain / presentation layering. Riverpod providers serve as the glue between features.

## Page Designs

### 1. Bookshelf (Home)

- Single-page navigation: bookshelf is the main page
- Top AppBar: logo/title on left, settings gear + avatar button on right
- Book grid: 3 columns, each card shows cover + title + progress bar
- Long press on book card → context menu (delete, details)
- FAB (bottom-right) → BottomSheet for file upload/import
- Pull-to-refresh syncs cloud bookshelf
- Index status indicator on each book card

### 2. Reader (Core)

**Immersive mode (default)**:
- Full-screen WebView rendering EPUB HTML content
- No toolbars visible
- Vertical scrolling
- TTS floating button in bottom-right corner
- Long press to select text → floating menu (highlight, note, translate, ask AI)

**Tap center 1/3 of screen → show toolbars**:
- Top bar: back button, chapter title, TOC button
- Bottom bar:
  - Tool row: font size (Aa), theme toggle, translate, settings
  - Chapter progress slider with prev/next chapter buttons
- Content area dimmed with semi-transparent overlay
- Tap again or tap overlay to dismiss

**Screen tap zones** (optional):
- Left 1/3 tap → previous page
- Center 1/3 tap → toggle toolbar
- Right 1/3 tap → next page

### 3. TTS Controls

**Floating button states**:
- Idle: speaker icon
- Playing: animated sound wave icon + current sentence number

**Control panel (BottomSheet on tap)**:
- Current sentence preview
- Playback controls: previous sentence / play-pause / next sentence
- Speed slider (0.5x - 2x)
- Voice selector dropdown
- Emotion type selector (neutral, warm, excited, serious, suspense)
- Download chapter audio button

### 4. Translation & Bilingual Reading

**AI Translation** (triggered from toolbar or text selection):
- Full chapter translation: toolbar "translate" button → BottomSheet showing translation progress + result
- Selected text translation: selection menu "Translate" → inline popup with translation

**Bilingual reading mode**:
- Toggle from toolbar settings → splits WebView content into original + translated side-by-side (portrait) or top-bottom layout
- Bilingual offset synchronization maintained via backend paragraph IDs
- Same implementation as web: backend returns aligned bilingual HTML, rendered in WebView

### 5. Highlight & Annotations

- Long press to select text in WebView (native text selection)
- Floating menu appears above selection: [Highlight] [Note] [Translate] [Ask AI]
- 4 highlight colors: yellow, green, blue, pink (matching web)
- Communication via JS Bridge between WebView and Flutter
- Highlights persisted to backend API

### 6. Profile Page

- Accessed via avatar button on bookshelf AppBar
- User info card (avatar, username, email)
- Reading stats: total hours, streak days, books count
- Reading heatmap visualization
- Settings list:
  - AI model configuration
  - Voice preferences
  - Theme settings
  - About
  - Logout

## WebView ↔ Flutter Communication

### JS Bridge Architecture

**Flutter → WebView** (via `evaluateJavascript`):
- Switch theme (modify CSS variables)
- Adjust font size
- Jump to chapter
- Add/remove highlight markers
- Highlight current sentence during TTS (karaoke effect)
- Scroll to specific paragraph position

**WebView → Flutter** (via `JavaScriptChannel`):
- Text selection → pass selection coordinates + text content
- Scroll position change → update reading progress
- Center screen tap → notify Flutter to toggle toolbar
- Internal link click → notify Flutter to navigate

### Communication Protocol

Messages passed as JSON through the bridge:

```dart
// Flutter → WebView
webViewController.evaluateJavascript('''
  window.flutterBridge.setTheme("night");
  window.flutterBridge.setFontSize(18);
  window.flutterBridge.highlightSentence(5);
  window.flutterBridge.scrollToParagraph("p-12");
  window.flutterBridge.addHighlight({id: "h1", start: 10, end: 25, color: "yellow"});
''');

// WebView → Flutter (JavaScriptChannel "FlutterChannel")
FlutterChannel.postMessage(JSON.stringify({
  type: "textSelected",
  data: { text: "selected text", rect: {x, y, w, h} }
}));
FlutterChannel.postMessage(JSON.stringify({
  type: "scrollProgress",
  data: { progress: 0.45, paragraphId: "p-12" }
}));
FlutterChannel.postMessage(JSON.stringify({
  type: "centerTap"
}));
```

## Data Flow

### API Integration

All endpoints shared with existing FastAPI backend:
- `/auth/*` — JWT auth, guest mode
- `/books/*` — book CRUD
- `/chapters/*` — chapter HTML content
- `/tts/*` — speech synthesis
- `/voices/*` — available voices
- `/highlights/*` — annotation CRUD
- `/reading/*` — progress & statistics
- `/ai-translate/*` — AI translation
- `/ai-chat/*` — AI Q&A
- `/ai-config/*` — user AI model config

### Local Cache Strategy

| Data | Storage | Sync |
|------|---------|------|
| Auth tokens | flutter_secure_storage | — |
| Reading progress | Hive | Periodic sync to backend |
| Visited chapters | Hive | Local only |
| TTS audio cache | File system + Hive index | On-demand download |
| Theme/font prefs | Hive | Sync to backend on change |
| User preferences | Hive | Sync on login |

### TTS Playback Flow

1. User taps play
2. `ttsProvider` requests `/tts/synthesize` from backend
3. Backend returns `{ audio_url, word_timestamps[] }`
4. `just_audio` loads and plays audio URL
5. Playback position callback → match `word_timestamps` → JS Bridge updates highlight
6. Current sentence finishes → preload next sentence audio (buffer strategy matches web)

## Theme System

### Dual-Layer Theming

**Flutter layer** (native UI: toolbars, bookshelf, panels):
- 4 `ThemeData` + `ColorScheme` definitions
- Global switch via `themeProvider`
- Persisted to Hive, synced to backend for logged-in users

**WebView layer** (reading content):
- CSS variable injection via JS (`--background`, `--foreground`, etc.)
- Same OKLch color values as web client for visual consistency

```
themeProvider change
    ├─→ Flutter UI rebuilds (ThemeData)
    └─→ evaluateJS('setTheme("night")') → WebView CSS variables update
```

### 4 Themes
- **Day**: light background, dark text
- **Night**: dark background, light text
- **Eye-care**: warm yellowish tones
- **Fresh-green**: soft green tones

## Platform Adaptation

### iOS
- Safe Area for notch/Dynamic Island
- CupertinoPageRoute transitions (swipe-back gesture)
- Status bar color follows theme
- Hide status bar in immersive reading mode

### Android
- Edge-to-edge fullscreen (transparent nav/status bars)
- Material 3 BottomSheet and FAB styling
- System back gesture compatibility
- Android 13+ predictive back animation

### Universal
- Landscape → auto dual-column layout (tablet/landscape phone)
- Screen rotation preserves reading position
- Dark mode follows system (overridable)
- Font scaling respects system accessibility settings

## Error Handling

- **Network errors**: Global Dio interceptor + Toast notification + offline cache fallback
- **Token expiry**: Interceptor auto-refresh, redirect to login on failure
- **WebView load failure**: Retry button + error placeholder page
- **TTS synthesis failure**: Toast + skip current sentence and continue
