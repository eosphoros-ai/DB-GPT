import { getModelIcon } from '@/utils/constants';
import Image from 'next/image';
import React, { memo, useMemo } from 'react';

const ModelIcon: React.FC<{ width?: number; height?: number; model?: string }> = ({ width, height, model }) => {
  const iconSrc = useMemo(() => {
    return getModelIcon(model || 'huggingface');
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
