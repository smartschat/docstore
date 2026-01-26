/**
 * Camera service for document scanning
 * Handles getUserMedia, capture, and orientation
 */

export interface CameraStream {
  stream: MediaStream;
  videoTrack: MediaStreamTrack;
  facingMode: 'user' | 'environment' | 'unknown';
  requestedFacingMode: 'user' | 'environment';
}

export interface CaptureOptions {
  maxWidth?: number;
  maxHeight?: number;
  quality?: number;
}

const DEFAULT_CAPTURE_OPTIONS: CaptureOptions = {
  maxWidth: 2000,
  maxHeight: 2000,
  quality: 0.85,
};

/**
 * Check if camera API is available
 */
export function isCameraSupported(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

/**
 * Get available video input devices
 */
export async function getVideoDevices(): Promise<MediaDeviceInfo[]> {
  if (!navigator.mediaDevices?.enumerateDevices) {
    return [];
  }

  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === 'videoinput');
}

/**
 * Start camera stream with preference for rear camera
 */
export async function startCamera(preferredFacingMode: 'user' | 'environment' = 'environment'): Promise<CameraStream> {
  if (!isCameraSupported()) {
    throw new Error('Camera not supported on this device');
  }

  // Try preferred facing mode first
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: preferredFacingMode },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
      audio: false,
    });

    const videoTrack = stream.getVideoTracks()[0];
    const settings = videoTrack.getSettings();
    const facingMode = (settings.facingMode as 'user' | 'environment') || 'unknown';

    return { stream, videoTrack, facingMode, requestedFacingMode: preferredFacingMode };
  } catch (error) {
    // If preferred mode fails, try any camera
    console.warn(`Failed to get ${preferredFacingMode} camera, trying any camera:`, error);

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
      audio: false,
    });

    const videoTrack = stream.getVideoTracks()[0];
    return { stream, videoTrack, facingMode: 'unknown', requestedFacingMode: preferredFacingMode };
  }
}

/**
 * Switch to the other camera (front/back)
 * Uses requestedFacingMode to reliably toggle even when browser doesn't report facingMode
 */
export async function switchCamera(currentRequestedFacingMode: 'user' | 'environment'): Promise<CameraStream> {
  const newFacingMode = currentRequestedFacingMode === 'user' ? 'environment' : 'user';
  return startCamera(newFacingMode);
}

/**
 * Stop all tracks in a media stream
 */
export function stopAllTracks(stream: MediaStream | null): void {
  if (!stream) return;

  stream.getTracks().forEach((track) => {
    track.stop();
  });
}

/**
 * Get the current device orientation correction
 * Returns rotation needed to correct the image (0, 90, 180, 270)
 *
 * Uses screen.orientation.type to determine physical orientation,
 * which works correctly on both portrait-native phones and landscape-native tablets.
 * Falls back to matchMedia for devices without screen.orientation API.
 */
function getOrientationCorrection(videoWidth: number, videoHeight: number): number {
  // Determine device's current physical orientation
  let deviceIsPortrait = true;
  let isSecondary = false; // secondary = upside-down or rotated the other way

  if (typeof screen !== 'undefined' && screen.orientation?.type) {
    // Modern API - type directly tells us portrait vs landscape
    const type = screen.orientation.type;
    deviceIsPortrait = type.startsWith('portrait');
    isSecondary = type.endsWith('secondary');
  } else if (typeof window !== 'undefined' && window.matchMedia) {
    // Fallback using matchMedia - works on older devices including landscape-native iPads
    // matchMedia reflects actual viewport orientation regardless of device's natural orientation
    deviceIsPortrait = window.matchMedia('(orientation: portrait)').matches;
    // Cannot reliably detect secondary (upside-down) without screen.orientation,
    // so we default to primary orientation (isSecondary = false)
  }

  const isVideoLandscape = videoWidth > videoHeight;
  const isVideoPortrait = videoHeight > videoWidth;

  // Case 1: Device in portrait, video is landscape (typical mobile camera)
  // Need to rotate video to match portrait display
  if (deviceIsPortrait && isVideoLandscape) {
    return isSecondary ? 270 : 90;
  }

  // Case 2: Device in landscape, video is portrait
  // Need to rotate video to match landscape display
  if (!deviceIsPortrait && isVideoPortrait) {
    return isSecondary ? 90 : 270;
  }

  // Case 3: Orientations match but device is in secondary (upside-down) position
  if (isSecondary) {
    return 180;
  }

  // Case 4: Orientations match and device is in primary position
  return 0;
}

/**
 * Capture image from video element to a Blob
 * Handles orientation and downscaling
 */
export async function captureImage(
  video: HTMLVideoElement,
  options: CaptureOptions = {}
): Promise<Blob> {
  const opts = { ...DEFAULT_CAPTURE_OPTIONS, ...options };

  // Get video dimensions
  const videoWidth = video.videoWidth;
  const videoHeight = video.videoHeight;

  if (!videoWidth || !videoHeight) {
    throw new Error('Video not ready for capture');
  }

  // Check if rotation is needed
  const rotation = getOrientationCorrection(videoWidth, videoHeight);
  const needsSwap = rotation === 90 || rotation === 270;

  // For 90/270 rotation, swap width and height for the output
  let sourceWidth = needsSwap ? videoHeight : videoWidth;
  let sourceHeight = needsSwap ? videoWidth : videoHeight;

  // Calculate scaled dimensions while maintaining aspect ratio
  let targetWidth = sourceWidth;
  let targetHeight = sourceHeight;

  if (opts.maxWidth && targetWidth > opts.maxWidth) {
    const scale = opts.maxWidth / targetWidth;
    targetWidth = opts.maxWidth;
    targetHeight = Math.round(targetHeight * scale);
  }

  if (opts.maxHeight && targetHeight > opts.maxHeight) {
    const scale = opts.maxHeight / targetHeight;
    targetHeight = opts.maxHeight;
    targetWidth = Math.round(targetWidth * scale);
  }

  // Create canvas with correct dimensions for the output
  const canvas = document.createElement('canvas');
  canvas.width = targetWidth;
  canvas.height = targetHeight;

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Failed to get canvas context');
  }

  // Apply rotation if needed
  if (rotation !== 0) {
    ctx.translate(targetWidth / 2, targetHeight / 2);
    ctx.rotate((rotation * Math.PI) / 180);

    // Calculate draw dimensions based on rotation
    let drawWidth: number;
    let drawHeight: number;
    if (needsSwap) {
      // 90° or 270° rotation - swap dimensions
      drawWidth = targetHeight;
      drawHeight = targetWidth;
    } else {
      // 180° rotation - keep dimensions
      drawWidth = targetWidth;
      drawHeight = targetHeight;
    }

    ctx.drawImage(video, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
  } else {
    ctx.drawImage(video, 0, 0, targetWidth, targetHeight);
  }

  // Convert to blob
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error('Failed to create blob from canvas'));
        }
      },
      'image/jpeg',
      opts.quality
    );
  });
}

/**
 * Process an image file (from file input) and return a properly oriented blob
 * Uses createImageBitmap for EXIF orientation handling
 */
export async function processImageFile(file: File, options: CaptureOptions = {}): Promise<Blob> {
  const opts = { ...DEFAULT_CAPTURE_OPTIONS, ...options };

  // Create image bitmap with automatic orientation correction
  const imageBitmap = await createImageBitmap(file, {
    imageOrientation: 'from-image',
  });

  // Calculate scaled dimensions
  let targetWidth = imageBitmap.width;
  let targetHeight = imageBitmap.height;

  if (opts.maxWidth && targetWidth > opts.maxWidth) {
    const scale = opts.maxWidth / targetWidth;
    targetWidth = opts.maxWidth;
    targetHeight = Math.round(targetHeight * scale);
  }

  if (opts.maxHeight && targetHeight > opts.maxHeight) {
    const scale = opts.maxHeight / targetHeight;
    targetHeight = opts.maxHeight;
    targetWidth = Math.round(targetWidth * scale);
  }

  // Draw to canvas
  const canvas = document.createElement('canvas');
  canvas.width = targetWidth;
  canvas.height = targetHeight;

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Failed to get canvas context');
  }

  ctx.drawImage(imageBitmap, 0, 0, targetWidth, targetHeight);
  imageBitmap.close();

  // Convert to blob
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error('Failed to create blob from canvas'));
        }
      },
      'image/jpeg',
      opts.quality
    );
  });
}

/**
 * Create object URL for a blob
 */
export function createObjectURL(blob: Blob): string {
  return URL.createObjectURL(blob);
}

/**
 * Revoke object URL to free memory
 */
export function revokeObjectURL(url: string): void {
  URL.revokeObjectURL(url);
}
