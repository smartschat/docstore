/**
 * Camera service for document scanning
 * Handles getUserMedia, capture, and orientation
 */

export interface CameraStream {
  stream: MediaStream;
  videoTrack: MediaStreamTrack;
  facingMode: 'user' | 'environment' | 'unknown';
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

    return { stream, videoTrack, facingMode };
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
    return { stream, videoTrack, facingMode: 'unknown' };
  }
}

/**
 * Switch to the other camera (front/back)
 */
export async function switchCamera(currentFacingMode: 'user' | 'environment' | 'unknown'): Promise<CameraStream> {
  const newFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
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

  // Calculate scaled dimensions while maintaining aspect ratio
  let targetWidth = videoWidth;
  let targetHeight = videoHeight;

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

  // Create canvas and draw video frame
  const canvas = document.createElement('canvas');
  canvas.width = targetWidth;
  canvas.height = targetHeight;

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Failed to get canvas context');
  }

  // Draw with proper scaling
  ctx.drawImage(video, 0, 0, targetWidth, targetHeight);

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
