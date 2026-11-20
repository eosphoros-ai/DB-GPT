import { DatabaseOutlined } from '@ant-design/icons';
import Image from 'next/image';
import styles from './database.module.css';

export default function DatabaseTypeIcon({
  icon,
  label,
  compact = false,
}: {
  icon?: string;
  label: string;
  compact?: boolean;
}) {
  return (
    <span className={compact ? styles.compactIcon : styles.databaseIcon}>
      {icon ? (
        <Image src={icon} alt={label} width={compact ? 20 : 32} height={compact ? 20 : 32} />
      ) : (
        <DatabaseOutlined />
      )}
    </span>
  );
}
