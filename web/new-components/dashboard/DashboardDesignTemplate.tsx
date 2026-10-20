import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import SkillPreview from '@/new-components/skills/SkillPreview';
import { ArrowRightOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import { Button, Modal } from 'antd';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { dashboardTemplatePrompt } from './dashboard-template-entry';
import styles from './DashboardGallery.module.css';

export default function DashboardDesignTemplate({
  name,
  favorite,
  onFavorite,
}: {
  name: string;
  favorite: boolean;
  onFavorite: () => void;
}) {
  useDashboardTranslation();
  const design = ADAPTED_SKILLS[name];
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const use = () =>
    void router.push({
      pathname: '/dashboards/new',
      query: {
        creation_mode: 'dashboard',
        skill: name,
        skill_prompt: dashboardTemplatePrompt(name),
      },
    });
  return (
    <>
      <article className={`${styles.card} ${styles.designCard}`} data-design-template={name}>
        <button
          type='button'
          className={styles.cover}
          onClick={() => setOpen(true)}
          aria-label={dt('预览模板 {{value0}}', { value0: dt(design.title) })}
        >
          <SkillPreview name={name} />
          <span className={styles.designLabel}>{dt('风格示意')}</span>
          <span className={styles.coverAction}>{dt('查看风格')}</span>
        </button>
        <button
          type='button'
          className={styles.favorite}
          aria-label={dt('{{value0}}模板 {{value1}}', {
            value0: favorite ? dt('取消收藏') : dt('收藏'),
            value1: dt(design.title),
          })}
          aria-pressed={favorite}
          onClick={onFavorite}
        >
          {favorite ? <StarFilled /> : <StarOutlined />}
        </button>
        <div className={styles.cardTitle}>
          <button type='button' onClick={() => setOpen(true)}>
            {dt(design.title)}
          </button>
        </div>
        <p className={styles.description}>{dt(design.description)}</p>
        <div className={styles.meta}>
          <span>{dt('风格技能 · 连接数据后生成')}</span>
          <button type='button' onClick={use} aria-label={dt('使用模板 {{value0}}', { value0: dt(design.title) })}>
            {dt('使用')} <ArrowRightOutlined />
          </button>
        </div>
      </article>
      <Modal
        open={open}
        title={dt(design.title)}
        onCancel={() => setOpen(false)}
        width={800}
        footer={
          <Button type='primary' onClick={use}>
            {dt('选择数据并创建看板')}
          </Button>
        }
      >
        <div className={styles.designPreview}>
          <SkillPreview name={name} />
        </div>
        <p className='mt-4 text-[var(--app-muted)]'>{dt(design.description)}</p>
        <p className='mt-2 text-xs text-[var(--app-muted)]'>
          {dt('上方为风格示意。创建时使用你选择的数据，保留指标的真实口径与单位。')}
        </p>
      </Modal>
    </>
  );
}
