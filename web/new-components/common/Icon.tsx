import Icon, { ApiOutlined, CloudDownloadOutlined, CloudUploadOutlined, FireOutlined } from '@ant-design/icons';
import type { ComponentProps } from 'react';

const localIcons = {
  'icon-hot': FireOutlined,
  'icon-plugin': ApiOutlined,
  'icon-publish-cloud': CloudUploadOutlined,
  'icon-unPublish-cloud': CloudDownloadOutlined,
};

function TemperatureSvg() {
  return (
    <svg viewBox='0 0 24 24' width='1em' height='1em' fill='none' stroke='currentColor' strokeWidth='1.8'>
      <path d='M9 14.5V5a3 3 0 0 1 6 0v9.5a5 5 0 1 1-6 0Z' />
      <path d='M12 8v9' />
      <circle cx='12' cy='18' r='1.5' fill='currentColor' stroke='none' />
    </svg>
  );
}

type Props = Omit<ComponentProps<typeof Icon>, 'ref'> & {
  type: keyof typeof localIcons | 'icon-icons-temperature';
};

// Render the app's icon set locally so a third-party script cannot break it.
export default function IconFont({ type, ...props }: Props) {
  if (type === 'icon-icons-temperature') return <Icon component={TemperatureSvg} {...props} />;
  const Component = localIcons[type];
  return <Component {...props} />;
}
