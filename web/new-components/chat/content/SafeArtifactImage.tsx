import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { getUserId } from '@/utils/storage';
import React, { useEffect, useState } from 'react';
import { ArtifactItem } from './ManusLeftPanel';

const resolveImageUrl = (src: string): string => {
  if (!src || src === '[object Object]') return '';
  if (/^https?:\/\//.test(src)) return src;
  if (src.startsWith('/images/')) {
    const base = process.env.API_BASE_URL || '';
    return base ? `${base}${src}` : src;
  }
  return src;
};

const resolveArtifactImageSrc = async (content: unknown): Promise<string> => {
  if (typeof content === 'string') {
    return resolveImageUrl(content);
  }
  if (content && typeof content === 'object') {
    const obj = content as Record<string, unknown>;
    if (typeof obj.file_path === 'string' && obj.file_path) {
      const base = process.env.API_BASE_URL || '';
      const downloadUrl = `${base}/api/v1/agent/files/download?file_path=${encodeURIComponent(obj.file_path)}`;
      const resp = await fetch(downloadUrl, {
        headers: { [HEADER_USER_ID_KEY]: getUserId() || '001' },
      });
      if (!resp.ok) throw new Error(`download failed: ${resp.status}`);
      const blob = await resp.blob();
      return URL.createObjectURL(blob);
    }
    const url = obj.url || obj.src;
    if (typeof url === 'string') return resolveImageUrl(url);
  }
  return resolveImageUrl(String(content ?? ''));
};

/** Loads agent/static images with auth headers for file_path artifacts. */
const SafeArtifactImage: React.FC<{ artifact: ArtifactItem; className?: string; style?: React.CSSProperties }> = ({
  artifact,
  className,
  style,
}) => {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let blobUrl: string | null = null;
    let cancelled = false;

    (async () => {
      try {
        const resolved = await resolveArtifactImageSrc(artifact.content);
        if (cancelled) {
          if (resolved.startsWith('blob:')) URL.revokeObjectURL(resolved);
          return;
        }
        if (!resolved) {
          setFailed(true);
          return;
        }
        if (resolved.startsWith('blob:')) blobUrl = resolved;
        setSrc(resolved);
        setFailed(false);
      } catch (e) {
        console.warn('SafeArtifactImage:', e);
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [artifact.content, artifact.id]);

  if (failed || !src) {
    return (
      <div className='text-sm text-gray-500 dark:text-gray-400 p-6 text-center'>
        Не удалось загрузить изображение. Попробуйте «Скачать» в списке файлов.
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={artifact.name || 'Image preview'}
      className={className}
      style={style}
      onError={() => setFailed(true)}
    />
  );
};

export default SafeArtifactImage;
