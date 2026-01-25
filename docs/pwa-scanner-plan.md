# PWA Document Scanner Feature

## Overview
Add a mobile-friendly document scanner to DocStore that allows users to capture multi-page documents with their camera, combine into a PDF, and upload.

## New Files

```
frontend/
├── src/lib/
│   ├── components/scanner/
│   │   ├── ScannerModal.svelte      # Main modal orchestrating the flow
│   │   ├── CameraView.svelte        # Camera capture with getUserMedia
│   │   ├── PagePreview.svelte       # Preview after capture (accept/retake/done)
│   │   ├── PageReview.svelte        # Multi-page review with reorder/delete
│   │   └── PageThumbnail.svelte     # Draggable thumbnail component
│   ├── services/
│   │   ├── camera.ts                # Camera API wrapper
│   │   └── pdf-generator.ts         # PDF generation with pdf-lib
│   └── stores/
│       └── scanner.ts               # Scanner state management
├── static/
│   ├── manifest.json                # PWA manifest
│   ├── sw.js                        # Minimal service worker (required for install prompt)
│   └── icons/
│       ├── icon-192.png
│       ├── icon-512.png
│       ├── icon-maskable-192.png    # Maskable icon for Android
│       └── apple-touch-icon.png
```

## Modified Files

- `frontend/src/app.html` - Add PWA meta tags + manifest link
- `frontend/src/routes/documents/+page.svelte` - Add Scan button + ScannerModal
- `frontend/src/routes/+layout.svelte` - Register service worker
- `frontend/package.json` - Add pdf-lib dependency

## User Flow

```
[Scan Button] → Camera View → Capture → Preview
                                          ↓
                              [Retake] ← [Add Page] → Camera (repeat)
                                          ↓
                                       [Done]
                                          ↓
                              Page Review (thumbnails, reorder, delete)
                                          ↓
                              [Save as PDF] → Upload → Document Detail
```

## Implementation Order

### Phase 1: PWA Foundation
1. Create `static/manifest.json` with required fields:
   - `name`, `short_name`, `start_url: "/"`
   - `display: "standalone"`, `background_color`, `theme_color`
   - `icons` array with 192px, 512px, and maskable variants
2. Create icons (192px, 512px, maskable, apple-touch-icon)
3. Update `app.html`:
   - `<link rel="manifest" href="/manifest.json">`
   - `<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">`
   - `<meta name="theme-color" content="#0284c7">`
   - `<meta name="apple-mobile-web-app-capable" content="yes">`
4. Create minimal `sw.js` at root scope (fetch passthrough - required for Android install prompt)
5. Register service worker in `+layout.svelte` **inside `onMount`** (client-only to avoid SSR crash)

### Phase 2: Services
1. `npm install pdf-lib`
2. Create `camera.ts`:
   - getUserMedia wrapper with `facingMode: { ideal: 'environment' }` (fallback to any camera)
   - Capture to **Blob** (not data URL)
   - Downscale to max 2000px on capture
   - **Orientation handling**: Read video track settings, apply rotation transform on canvas
   - `playsinline` attribute for iOS Safari
   - **Lifecycle**: `stopAllTracks()` function, call on modal close + `visibilitychange` event
3. Create `pdf-generator.ts`:
   - Convert blob array to PDF
   - **Page sizing**: Fit images to A4 (595×842 points) maintaining aspect ratio
   - Use dynamic import for pdf-lib (lazy load, client-side only)
   - **Sequential processing**: Embed one page at a time, release blob after each
   - Use `requestIdleCallback` or `setTimeout(0)` between pages to avoid UI freeze
   - Progress callback: `onProgress(current, total)`
4. Create `scanner.ts` store:
   - Store pages as `Blob[]` with object URLs for display
   - **Page limit**: Max 20 pages with user warning
   - **Memory cleanup**: `URL.revokeObjectURL()` on page delete, after PDF upload, and on modal close
   - State machine: idle/camera/preview/review/generating/uploading

### Phase 3: Components
1. `CameraView.svelte`:
   - Video preview with `playsinline autoplay muted`
   - Capture button (user gesture required)
   - Camera switch button (if multiple cameras)
   - **Fallback**: `<input type="file" accept="image/jpeg,image/png,image/heic" capture="environment">`
   - **HEIC handling**: Browser native - iOS Safari decodes HEIC, show error on unsupported browsers
   - **EXIF orientation**: Use `createImageBitmap()` with `imageOrientation: 'from-image'` (modern browsers auto-correct)
   - Permission denied UI with instructions
   - **Cleanup**: Stop tracks on unmount via `onDestroy`
   - **Visibility**: Pause/resume on `visibilitychange`
   - **SSR safety**: All camera/navigator APIs inside `onMount` or guarded by `browser`
2. `PagePreview.svelte`:
   - Image preview from object URL
   - Retake / Add Page / Done buttons
   - Page count indicator
3. `PageThumbnail.svelte`:
   - Thumbnail with page number badge
   - Delete button (top-right X)
   - **Drag handle**: `touch-action: none` on handle element
4. `PageReview.svelte`:
   - Grid of thumbnails (2 cols mobile, 4 cols desktop)
   - **Pointer events drag**: `pointerdown/move/up` with `preventDefault` on handle
   - Move up/down buttons as accessible fallback
   - Add Page / Save buttons
   - Page count: "X pages" with warning if near limit
5. `ScannerModal.svelte`:
   - Full-screen on mobile, large modal on desktop
   - Focus trap, ESC to close
   - ARIA labels for accessibility
   - **Cleanup on close**: Stop camera, revoke all object URLs

### Phase 4: Integration
1. Add Scan button to documents page header
2. Include ScannerModal component
3. On save:
   - Generate PDF blob
   - Convert to File: `new File([blob], 'scan-YYYY-MM-DD-HHMMSS.pdf', {type: 'application/pdf'})`
   - Upload via existing `uploadDocument(file)`
   - Revoke all object URLs
   - Reload documents list

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PDF library | pdf-lib (lazy loaded) | TypeScript, smaller bundle, dynamic import |
| Image storage | Blob + object URLs | Avoid memory crashes from base64 |
| Image size | Max 2000px, JPEG 85% | Balance quality for OCR vs file size |
| PDF page size | A4 (595×842 pt) | Standard size, images fit maintaining aspect ratio |
| Page limit | 20 pages max | Prevent memory crashes on mobile |
| Drag-drop | Pointer events + touch-action:none | Avoid scroll conflicts on mobile |
| Service worker | Minimal fetch passthrough | Required for Android install prompt |
| Camera fallback | `<input capture>` | Works when getUserMedia unavailable |
| HEIC files | Browser native, error if unsupported | No extra deps, iOS Safari handles HEIC natively |
| Base path | Root (/) hardcoded | DocStore always deployed at root, no subpath |
| Upload format | Convert Blob → File | `new File([blob], 'scan.pdf', {type: 'application/pdf'})` |

## iOS Considerations
- No automatic "Add to Home Screen" prompt (manual via Share menu)
- Requires `playsinline` attribute on video element
- Camera permissions may reset between sessions
- May return HEIC images from file input - need conversion
- Video orientation may differ from display - check track settings

## Verification

1. **PWA Install**:
   - Android Chrome: Install prompt appears after ~30s engagement
   - iOS Safari: Can add via Share → Add to Home Screen
2. **Camera**: Grant permission → rear camera activates → capture works
3. **Camera cleanup**: Close modal → camera LED turns off, can reopen
4. **Fallback**: Block camera permission → file picker appears
5. **Orientation**: Capture in portrait and landscape → images display correctly
6. **Multi-page**: Capture 5 pages → reorder via touch drag → delete one → save
7. **PDF output**: Generated PDF has A4 pages, images properly sized
8. **Upload**: PDF appears in documents list, OCR processes automatically
9. **Memory**: Capture 15 pages without browser crash (test on real iOS device)
10. **Page limit**: At 20 pages, show warning and disable "Add Page"

## Unit Tests

Add tests in `frontend/src/lib/__tests__/`:

1. `scanner.test.ts` - Scanner store:
   - State transitions (idle → camera → preview → review → uploading)
   - Page add/delete/reorder operations
   - Page limit enforcement (max 20)
   - Object URL cleanup on delete

2. `pdf-generator.test.ts` - PDF generation:
   - Single page PDF creation
   - Multi-page PDF with correct page order
   - A4 sizing and aspect ratio
   - Progress callback invocation

## Future Enhancements (v2)
- Manual crop/rotate in PagePreview
- Edge detection / auto-deskew
- Offline queue with IndexedDB
- Service worker caching for offline app shell
- Web Worker for PDF generation (true background processing)
