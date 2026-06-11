import fallbackCopy from 'copy-to-clipboard';

type ClipboardLike = {
  writeText: (text: string) => Promise<void>;
};

type CopyTextOptions = {
  clipboard?: ClipboardLike;
  fallbackCopy?: (text: string) => boolean;
};

export async function copyText(text: string, options: CopyTextOptions = {}): Promise<boolean> {
  if (!text) return false;

  const clipboard = options.clipboard ?? (typeof navigator !== 'undefined' ? navigator.clipboard : undefined);
  const copyFallback = options.fallbackCopy ?? fallbackCopy;

  if (clipboard?.writeText) {
    try {
      await clipboard.writeText(text);
      return true;
    } catch (_e) {
      // HTTP deployments and browser permission policies can block Clipboard API.
    }
  }

  try {
    return copyFallback(text);
  } catch (_e) {
    return false;
  }
}
