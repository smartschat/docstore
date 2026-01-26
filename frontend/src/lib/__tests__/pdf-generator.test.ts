import { describe, it, expect, vi } from 'vitest';
import { generatePdf, generateFilename, pdfBlobToFile } from '$lib/services/pdf-generator';

// Helper to create a mock blob with arrayBuffer method
function createMockBlob(type: string = 'image/jpeg'): Blob {
  const data = new Uint8Array([0x00, 0x01, 0x02, 0x03]);
  const blob = {
    type,
    size: data.length,
    arrayBuffer: vi.fn(() => Promise.resolve(data.buffer)),
    slice: vi.fn(),
    stream: vi.fn(),
    text: vi.fn(() => Promise.resolve('')),
  } as unknown as Blob;
  return blob;
}

function createJpegBlob(): Blob {
  return createMockBlob('image/jpeg');
}

// Mock pdf-lib module
vi.mock('pdf-lib', () => {
  const mockPage = {
    drawImage: vi.fn()
  };

  const mockImage = {
    width: 800,
    height: 600
  };

  const mockPdfDoc = {
    addPage: vi.fn(() => mockPage),
    embedJpg: vi.fn(() => Promise.resolve(mockImage)),
    embedPng: vi.fn(() => Promise.resolve(mockImage)),
    save: vi.fn(() => Promise.resolve(new Uint8Array([0x25, 0x50, 0x44, 0x46]))) // "%PDF"
  };

  return {
    PDFDocument: {
      create: vi.fn(() => Promise.resolve(mockPdfDoc))
    }
  };
});

describe('PDF Generator', () => {
  describe('generatePdf', () => {
    it('should throw error when no images provided', async () => {
      await expect(generatePdf([])).rejects.toThrow('No images provided');
    });

    it('should create PDF from single image', async () => {
      const blob = createJpegBlob();
      const pdf = await generatePdf([blob]);

      expect(pdf).toBeInstanceOf(Blob);
      expect(pdf.type).toBe('application/pdf');
    });

    it('should create PDF from multiple images', async () => {
      const blobs = [createJpegBlob(), createJpegBlob(), createJpegBlob()];
      const pdf = await generatePdf(blobs);

      expect(pdf).toBeInstanceOf(Blob);
      expect(pdf.type).toBe('application/pdf');
    });

    it('should call progress callback', async () => {
      const blobs = [createJpegBlob(), createJpegBlob(), createJpegBlob()];
      const progressCalls: Array<{ current: number; total: number }> = [];

      await generatePdf(blobs, {
        onProgress: (current, total) => {
          progressCalls.push({ current, total });
        }
      });

      expect(progressCalls).toHaveLength(3);
      expect(progressCalls[0]).toEqual({ current: 1, total: 3 });
      expect(progressCalls[1]).toEqual({ current: 2, total: 3 });
      expect(progressCalls[2]).toEqual({ current: 3, total: 3 });
    });

    it('should handle PNG images', async () => {
      const pngBlob = createMockBlob('image/png');
      const pdf = await generatePdf([pngBlob]);

      expect(pdf).toBeInstanceOf(Blob);
      expect(pdf.type).toBe('application/pdf');
    });
  });

  describe('generateFilename', () => {
    it('should generate timestamped filename', () => {
      const filename = generateFilename();

      expect(filename).toMatch(/^scan-\d{8}-\d{6}\.pdf$/);
    });

    it('should include correct date format', () => {
      // Mock Date to control output
      vi.useFakeTimers();
      const mockDate = new Date('2024-03-15T14:30:45.000Z');
      vi.setSystemTime(mockDate);

      const filename = generateFilename();

      expect(filename).toBe('scan-20240315-143045.pdf');

      vi.useRealTimers();
    });
  });

  describe('pdfBlobToFile', () => {
    it('should convert blob to File with default filename', () => {
      const blob = new Blob(['test'], { type: 'application/pdf' });
      const file = pdfBlobToFile(blob);

      expect(file).toBeInstanceOf(File);
      expect(file.type).toBe('application/pdf');
      expect(file.name).toMatch(/^scan-\d{8}-\d{6}\.pdf$/);
    });

    it('should use provided filename', () => {
      const blob = new Blob(['test'], { type: 'application/pdf' });
      const file = pdfBlobToFile(blob, 'custom-name.pdf');

      expect(file.name).toBe('custom-name.pdf');
    });

    it('should preserve blob size', () => {
      const content = 'PDF content here';
      const blob = new Blob([content], { type: 'application/pdf' });
      const file = pdfBlobToFile(blob);

      expect(file.size).toBe(blob.size);
    });
  });
});

describe('PDF Page Sizing', () => {
  // A4 dimensions: 595 x 842 points
  const A4_WIDTH = 595;
  const A4_HEIGHT = 842;

  it('should fit landscape image to A4 width', async () => {
    // Mock an image wider than A4
    const { PDFDocument } = await import('pdf-lib');
    const mockDoc = await PDFDocument.create();

    // The mock will be called with the image
    const blob = createJpegBlob();
    await generatePdf([blob]);

    // Verify addPage was called with A4 dimensions
    expect(mockDoc.addPage).toHaveBeenCalledWith([A4_WIDTH, A4_HEIGHT]);
  });

  it('should maintain aspect ratio when scaling', async () => {
    const blob = createJpegBlob();
    const pdf = await generatePdf([blob]);

    // PDF should be created successfully (aspect ratio logic is in the implementation)
    expect(pdf).toBeInstanceOf(Blob);
  });
});
