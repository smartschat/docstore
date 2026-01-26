/**
 * PDF generation service using pdf-lib
 * Converts image blobs to a multi-page PDF document
 */

// A4 dimensions in points (72 points per inch)
const A4_WIDTH = 595;
const A4_HEIGHT = 842;

export interface PdfGeneratorOptions {
  onProgress?: (current: number, total: number) => void;
  signal?: AbortSignal;
}

/**
 * Generate a PDF from an array of image blobs
 * Uses dynamic import for lazy loading
 */
export async function generatePdf(
  images: Blob[],
  options: PdfGeneratorOptions = {}
): Promise<Blob> {
  if (images.length === 0) {
    throw new Error('No images provided');
  }

  // Dynamic import for lazy loading (reduces initial bundle size)
  const { PDFDocument } = await import('pdf-lib');

  const pdfDoc = await PDFDocument.create();

  for (let i = 0; i < images.length; i++) {
    // Check for cancellation before processing each page
    if (options.signal?.aborted) {
      throw new DOMException('PDF generation aborted', 'AbortError');
    }

    // Report progress
    options.onProgress?.(i + 1, images.length);

    // Convert blob to array buffer
    const arrayBuffer = await images[i].arrayBuffer();

    // Embed image based on type
    let image;
    const type = images[i].type;

    if (type === 'image/png') {
      image = await pdfDoc.embedPng(arrayBuffer);
    } else {
      // Default to JPEG for all other types
      image = await pdfDoc.embedJpg(arrayBuffer);
    }

    // Calculate dimensions to fit A4 while maintaining aspect ratio
    const { width: imgWidth, height: imgHeight } = image;
    const imgAspect = imgWidth / imgHeight;
    const pageAspect = A4_WIDTH / A4_HEIGHT;

    let scaledWidth: number;
    let scaledHeight: number;

    if (imgAspect > pageAspect) {
      // Image is wider than A4 - fit to width
      scaledWidth = A4_WIDTH;
      scaledHeight = A4_WIDTH / imgAspect;
    } else {
      // Image is taller than A4 - fit to height
      scaledHeight = A4_HEIGHT;
      scaledWidth = A4_HEIGHT * imgAspect;
    }

    // Create page and center image
    const page = pdfDoc.addPage([A4_WIDTH, A4_HEIGHT]);
    const x = (A4_WIDTH - scaledWidth) / 2;
    const y = (A4_HEIGHT - scaledHeight) / 2;

    page.drawImage(image, {
      x,
      y,
      width: scaledWidth,
      height: scaledHeight,
    });

    // Yield to UI thread between pages to prevent freezing
    await new Promise((resolve) => {
      if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
        requestIdleCallback(() => resolve(undefined), { timeout: 100 });
      } else {
        setTimeout(resolve, 0);
      }
    });
  }

  // Check for cancellation before saving
  if (options.signal?.aborted) {
    throw new DOMException('PDF generation aborted', 'AbortError');
  }

  // Save PDF and return as blob
  const pdfBytes = await pdfDoc.save();
  return new Blob([new Uint8Array(pdfBytes)], { type: 'application/pdf' });
}

/**
 * Generate a timestamped filename for the scanned PDF
 */
export function generateFilename(): string {
  const now = new Date();
  const timestamp = now
    .toISOString()
    .replace(/[-:]/g, '')
    .replace('T', '-')
    .slice(0, 15);
  return `scan-${timestamp}.pdf`;
}

/**
 * Convert a PDF blob to a File object ready for upload
 */
export function pdfBlobToFile(blob: Blob, filename?: string): File {
  const name = filename || generateFilename();
  return new File([blob], name, { type: 'application/pdf' });
}
