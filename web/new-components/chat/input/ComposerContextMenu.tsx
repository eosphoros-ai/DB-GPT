import type { SuiteItem } from '@/types/suite';
import { suiteDisplayName } from '@/utils/suite-routing';
import {
  ApartmentOutlined,
  ApiOutlined,
  BookOutlined,
  CheckOutlined,
  DatabaseOutlined,
  PaperClipOutlined,
  PlusOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Button, Dropdown, Upload, type MenuProps, type UploadProps } from 'antd';
import { useTranslation } from 'react-i18next';
import styles from './ComposerContextMenu.module.css';
import SuiteHammerIcon from './SuiteHammerIcon';

function ExpertSuiteIcon({ className }: { className?: string }) {
  return (
    <span className={`anticon ${className || ''}`} aria-hidden='true'>
      <svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.7'>
        {[6, 18].flatMap(cx => [6, 18].map(cy => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r='4' />))}
      </svg>
    </span>
  );
}

interface Props {
  suites: SuiteItem[];
  selectedSuite?: string;
  onSelectSuite: (suite: SuiteItem) => void;
  onManageSuites: () => void;
  uploadProps: UploadProps;
  skillItems: MenuProps['items'];
  onViewSkills: () => void;
  onSelectDatabase: () => void;
  onSelectKnowledge: () => void;
  onSelectConnector: () => void;
  flowItems: MenuProps['items'];
}

/** Shared context picker for the home composer and an existing conversation. */
export default function ComposerContextMenu({
  suites,
  selectedSuite,
  onSelectSuite,
  onManageSuites,
  uploadProps,
  skillItems,
  onViewSkills,
  onSelectDatabase,
  onSelectKnowledge,
  onSelectConnector,
  flowItems,
}: Props) {
  const { t, i18n } = useTranslation();
  const enabledSuites = suites.filter(suite => suite.status === 'enabled');
  const items: MenuProps['items'] = [
    {
      key: 'upload',
      icon: <PaperClipOutlined />,
      label: (
        <Upload {...uploadProps}>
          <span className={styles.upload}>{t('add_from_local')}</span>
        </Upload>
      ),
    },
    { type: 'divider' },
    {
      key: 'skills',
      icon: (
        <span className='anticon'>
          <SuiteHammerIcon />
        </span>
      ),
      label: t('use_skill'),
      popupClassName: styles.submenu,
      children: [
        ...(skillItems || []),
        { type: 'divider' },
        { key: 'view-skills', icon: <SettingOutlined />, label: t('composer_view_skills'), onClick: onViewSkills },
      ],
    },
    {
      key: 'suites',
      icon: <ExpertSuiteIcon />,
      label: t('suite_reference_label'),
      popupClassName: styles.submenu,
      children: [
        ...enabledSuites.map(suite => ({
          key: `suite-${suite.name}`,
          icon: <ExpertSuiteIcon />,
          label: (
            <span className={styles.option} data-testid={`composer-suite-${suite.name}`}>
              <span className={styles.name}>{suiteDisplayName(suite, i18n.language)}</span>
              <span className={styles.description}>
                {(i18n.language.startsWith('en') && suite.manifest_snapshot?.description_en) ||
                  suite.manifest_snapshot?.description}
              </span>
              {suite.name === selectedSuite && <CheckOutlined className={styles.check} />}
            </span>
          ),
          onClick: () => onSelectSuite(suite),
        })),
        ...(!enabledSuites.length ? [{ key: 'empty-suites', label: t('composer_suites_empty'), disabled: true }] : []),
        { type: 'divider' as const },
        {
          key: 'manage-suites',
          icon: <SettingOutlined />,
          label: t('composer_view_suites'),
          onClick: onManageSuites,
        },
      ],
    },
    { type: 'divider' },
    { key: 'database', icon: <DatabaseOutlined />, label: t('use_database'), onClick: onSelectDatabase },
    { key: 'knowledge', icon: <BookOutlined />, label: t('use_knowledge'), onClick: onSelectKnowledge },
    { key: 'connector', icon: <ApiOutlined />, label: t('use_connector'), onClick: onSelectConnector },
    {
      key: 'taskflow',
      icon: <ApartmentOutlined />,
      label: t('taskflow'),
      popupClassName: styles.submenu,
      children: flowItems,
    },
  ];
  return (
    <Dropdown
      menu={{ items, selectedKeys: selectedSuite ? [`suite-${selectedSuite}`] : [] }}
      trigger={['click']}
      placement='topLeft'
      overlayClassName={styles.root}
    >
      <Button
        type='text'
        shape='circle'
        icon={<PlusOutlined />}
        aria-label={t('add_context')}
        data-testid='composer-context-trigger'
        className={styles.trigger}
      />
    </Dropdown>
  );
}
