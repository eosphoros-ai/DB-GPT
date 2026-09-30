const { existsSync, readdirSync, readFileSync, statSync } = require('node:fs');
const path = require('node:path');

/** Recursively collect generated HTML pages, returning an empty list for an absent directory. */
const listHtmlFiles = directory => {
  if (!existsSync(directory)) return [];
  const files = [];
  for (const entry of readdirSync(directory)) {
    const fullPath = path.join(directory, entry);
    if (statSync(fullPath).isDirectory()) {
      files.push(...listHtmlFiles(fullPath));
    } else if (entry.endsWith('.html')) {
      files.push(fullPath);
    }
  }
  return files;
};

/** Verify local Next asset references in server or exported HTML; throw for missing pages/assets and return verification counts. */
const verifyNextBuildAssets = (nextDirectory, { staticExport = false } = {}) => {
  const pagesDirectory = staticExport ? nextDirectory : path.join(nextDirectory, 'server', 'pages');
  const htmlFiles = listHtmlFiles(pagesDirectory);
  if (htmlFiles.length === 0) {
    throw new Error(`No prerendered pages found in ${pagesDirectory}`);
  }

  const missing = [];
  let assetReferences = 0;
  for (const htmlFile of htmlFiles) {
    const html = readFileSync(htmlFile, 'utf8');
    for (const match of html.matchAll(/(?:src|href)="\/_next\/([^"?#]+)(?:[?#][^"]*)?"/gu)) {
      assetReferences += 1;
      const relativeAsset = decodeURIComponent(match[1]).split('/').join(path.sep);
      const assetPath = path.join(nextDirectory, ...(staticExport ? ['_next'] : []), relativeAsset);
      if (!existsSync(assetPath)) {
        missing.push(`${path.relative(nextDirectory, htmlFile)} -> ${match[1]}`);
      }
    }
  }

  if (missing.length > 0) {
    throw new Error(
      `Next.js output contains ${missing.length} missing local asset reference(s):\n${missing
        .slice(0, 20)
        .map(item => `- ${item}`)
        .join('\n')}`,
    );
  }

  return { htmlFiles: htmlFiles.length, assetReferences };
};

module.exports = { verifyNextBuildAssets };
