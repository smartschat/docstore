import sharp from 'sharp';
import { writeFileSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const iconsDir = join(__dirname, '../static/icons');

// DocStore icon: A document with a scan line
function createIconSvg(size, maskable = false) {
  const padding = maskable ? size * 0.1 : 0;
  const innerSize = size - padding * 2;
  const bgColor = maskable ? '#0284c7' : 'none';

  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
    ${maskable ? `<rect width="${size}" height="${size}" fill="${bgColor}"/>` : ''}
    <g transform="translate(${padding}, ${padding})">
      <!-- Document background -->
      <rect x="${innerSize * 0.2}" y="${innerSize * 0.1}" width="${innerSize * 0.6}" height="${innerSize * 0.8}"
            rx="${innerSize * 0.04}" fill="white" stroke="#0284c7" stroke-width="${innerSize * 0.02}"/>

      <!-- Document lines -->
      <line x1="${innerSize * 0.3}" y1="${innerSize * 0.3}" x2="${innerSize * 0.7}" y2="${innerSize * 0.3}"
            stroke="#94a3b8" stroke-width="${innerSize * 0.02}" stroke-linecap="round"/>
      <line x1="${innerSize * 0.3}" y1="${innerSize * 0.45}" x2="${innerSize * 0.7}" y2="${innerSize * 0.45}"
            stroke="#94a3b8" stroke-width="${innerSize * 0.02}" stroke-linecap="round"/>
      <line x1="${innerSize * 0.3}" y1="${innerSize * 0.6}" x2="${innerSize * 0.55}" y2="${innerSize * 0.6}"
            stroke="#94a3b8" stroke-width="${innerSize * 0.02}" stroke-linecap="round"/>

      <!-- Scan line -->
      <line x1="${innerSize * 0.15}" y1="${innerSize * 0.75}" x2="${innerSize * 0.85}" y2="${innerSize * 0.75}"
            stroke="#0284c7" stroke-width="${innerSize * 0.025}" stroke-linecap="round">
        <animate attributeName="y1" values="${innerSize * 0.2};${innerSize * 0.8};${innerSize * 0.2}" dur="2s" repeatCount="indefinite"/>
        <animate attributeName="y2" values="${innerSize * 0.2};${innerSize * 0.8};${innerSize * 0.2}" dur="2s" repeatCount="indefinite"/>
      </line>
    </g>
  </svg>`;
}

// Simple static version for PNG export (no animation)
function createStaticIconSvg(size, maskable = false) {
  const padding = maskable ? size * 0.15 : size * 0.05;
  const innerSize = size - padding * 2;
  const bgColor = '#0284c7';

  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
    <!-- Background -->
    <rect width="${size}" height="${size}" fill="${bgColor}" rx="${maskable ? 0 : size * 0.15}"/>

    <g transform="translate(${padding}, ${padding})">
      <!-- Document background -->
      <rect x="${innerSize * 0.15}" y="${innerSize * 0.05}" width="${innerSize * 0.7}" height="${innerSize * 0.9}"
            rx="${innerSize * 0.05}" fill="white"/>

      <!-- Document lines -->
      <rect x="${innerSize * 0.25}" y="${innerSize * 0.2}" width="${innerSize * 0.5}" height="${innerSize * 0.06}"
            rx="${innerSize * 0.03}" fill="#cbd5e1"/>
      <rect x="${innerSize * 0.25}" y="${innerSize * 0.35}" width="${innerSize * 0.5}" height="${innerSize * 0.06}"
            rx="${innerSize * 0.03}" fill="#cbd5e1"/>
      <rect x="${innerSize * 0.25}" y="${innerSize * 0.5}" width="${innerSize * 0.35}" height="${innerSize * 0.06}"
            rx="${innerSize * 0.03}" fill="#cbd5e1"/>

      <!-- Camera/scan icon at bottom -->
      <circle cx="${innerSize * 0.5}" cy="${innerSize * 0.75}" r="${innerSize * 0.12}" fill="${bgColor}"/>
      <circle cx="${innerSize * 0.5}" cy="${innerSize * 0.75}" r="${innerSize * 0.06}" fill="white"/>
    </g>
  </svg>`;
}

async function generateIcon(size, filename, maskable = false) {
  const svg = createStaticIconSvg(size, maskable);
  const buffer = await sharp(Buffer.from(svg))
    .png()
    .toBuffer();
  writeFileSync(join(iconsDir, filename), buffer);
  console.log(`Generated: ${filename}`);
}

async function main() {
  mkdirSync(iconsDir, { recursive: true });

  await Promise.all([
    generateIcon(192, 'icon-192.png', false),
    generateIcon(512, 'icon-512.png', false),
    generateIcon(192, 'icon-maskable-192.png', true),
    generateIcon(512, 'icon-maskable-512.png', true),
    generateIcon(180, 'apple-touch-icon.png', false),
  ]);

  // Also create favicon
  const faviconSvg = createStaticIconSvg(32, false);
  const faviconBuffer = await sharp(Buffer.from(faviconSvg))
    .png()
    .toBuffer();
  writeFileSync(join(iconsDir, '../favicon.png'), faviconBuffer);
  console.log('Generated: favicon.png');

  console.log('All icons generated successfully!');
}

main().catch(console.error);
