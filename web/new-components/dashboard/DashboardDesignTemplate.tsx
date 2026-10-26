import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import SkillPreview from '@/new-components/skills/SkillPreview';
import { ArrowRightOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import { Button, Modal } from 'antd';
import { useRouter } from 'next/router';
import { useState } from 'react';
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
  const design = ADAPTED_SKILLS[name];
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const use = () =>
    void router.push({
      pathname: '/',
      query: {
        creation_mode: 'dashboard',
        skill: name,
        skill_prompt: `${design.prompt} 请创建原生可编辑数据看板。先结合我选择的数据源规划指标和筛选条件，所有数值来自实际查询。`,
      },
    });
  return (
    <>
      <article className={`${styles.card} ${styles.designCard}`} data-design-template={name}>
        <button
          type='button'
          className={styles.cover}
          onClick={() => setOpen(true)}
          aria-label={`预览模板 ${design.title}`}
        >
          <SkillPreview name={name} />
          <span className={styles.designLabel}>风格示意</span>
          <span className={styles.coverAction}>查看风格</span>
        </button>
        <button
          type='button'
          className={styles.favorite}
          aria-label={`${favorite ? '取消收藏' : '收藏'}模板 ${design.title}`}
          aria-pressed={favorite}
          onClick={onFavorite}
        >
          {favorite ? <StarFilled /> : <StarOutlined />}
        </button>
        <div className={styles.cardTitle}>
          <button type='button' onClick={() => setOpen(true)}>
            {design.title}
          </button>
        </div>
        <p className={styles.description}>{design.description}</p>
        <div className={styles.meta}>
          <span>风格技能 · 连接数据后生成</span>
          <button type='button' onClick={use} aria-label={`使用模板 ${design.title}`}>
            使用 <ArrowRightOutlined />
          </button>
        </div>
      </article>
      <Modal
        open={open}
        title={design.title}
        onCancel={() => setOpen(false)}
        width={800}
        footer={
          <Button type='primary' onClick={use}>
            选择数据并创建看板
          </Button>
        }
      >
        <div className={styles.designPreview}>
          <SkillPreview name={name} />
        </div>
        <p className='mt-4 text-[var(--app-muted)]'>{design.description}</p>
        <p className='mt-2 text-xs text-[var(--app-muted)]'>
          上方为风格示意。创建时使用你选择的数据，保留指标的真实口径与单位。
        </p>
      </Modal>
    </>
  );
}
