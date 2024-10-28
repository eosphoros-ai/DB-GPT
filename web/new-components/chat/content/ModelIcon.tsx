import { MODEL_ICON_DICT } from '@/utils/constants';
import Image from 'next/image';
import React, { memo, useMemo } from 'react';

const DEFAULT_ICON_URL = '/models/huggingface.svg';

const ModelIcon: React.FC<{ width?: number; height?: number; model?: string }> = ({ width, height, model }) => {
  const iconSrc = useMemo(() => {
    const formatterModal = model?.replaceAll('-', '_').split('_')[0];
    const dict = Object.keys(MODEL_ICON_DICT);
    for (let i = 0; i < dict.length; i++) {
      const element = dict[i];
      if (formatterModal?.includes(element)) {
        return MODEL_ICON_DICT[element];
      }
    }
    return DEFAULT_ICON_URL;
  }, [model]);

  if (!model) return null;

  return (
    <Image
      className='rounded-full border border-gray-200 object-contain bg-white inline-block'
      width={width || 24}
      height={height || 24}
      src={iconSrc}
      alt='llm'
      priority
    />
  );
};

export default memo(ModelIcon);
