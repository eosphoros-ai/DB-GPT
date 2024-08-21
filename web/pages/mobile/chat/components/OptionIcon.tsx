import Image from 'next/image';
import React, { memo } from 'react';

interface IProps {
  width?: number;
  height?: number;
  src: string;
  label: string;
  className?: string;
}
const OptionIcon: React.FC<IProps> = ({ width, height, src, label }) => {
  return <Image width={width || 14} height={height || 14} src={src} alt={label || 'db-icon'} priority />;
};

export default memo(OptionIcon);
