import Image from 'next/image';

interface IProps {
  width?: number;
  height?: number;
  src: string;
  label: string;
  className?: string;
}

function DBIcon({ src, label, width, height, className }: IProps) {
  return (
    <Image
      className={`w-11 h-11 rounded-full mr-4 border border-gray-200 object-contain bg-white ${className}`}
      width={width || 44}
      height={height || 44}
      src={src}
      alt={label || 'db-icon'}
    />
  );
}

export default DBIcon;
