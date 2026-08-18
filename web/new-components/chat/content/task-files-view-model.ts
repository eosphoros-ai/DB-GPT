/**
 * Pure view-model helpers for the task-files panel.
 *
 * The top-level tabs intentionally model the user's workflow: uploaded inputs
 * form one bucket, while generated artifacts are grouped by output type. This
 * keeps every file in exactly one tab and avoids a second layer of filters.
 */

export type TaskFileTab = 'all' | 'input' | 'document' | 'image' | 'code';
export type GeneratedTaskFileTab = Exclude<TaskFileTab, 'all' | 'input'>;
export type TaskFileTabNavigationKey = 'ArrowLeft' | 'ArrowRight' | 'Home' | 'End';

export interface TaskFileTabDefinition {
  key: TaskFileTab;
  label: string;
}

export interface TaskArtifactLike {
  name: string;
  type: string;
}

export const TASK_FILE_TABS: readonly TaskFileTabDefinition[] = Object.freeze([
  { key: 'all', label: '全部' },
  { key: 'input', label: '上传资料' },
  { key: 'document', label: '文档' },
  { key: 'image', label: '图片' },
  { key: 'code', label: '代码文件' },
]);

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']);
const CODE_EXTENSIONS = new Set(['py', 'js', 'ts', 'tsx', 'jsx', 'sql', 'sh', 'json', 'yaml', 'yml']);
const EMPTY_LABELS: Record<TaskFileTab, string> = {
  all: '暂无任务文件',
  input: '暂无上传资料',
  document: '暂无生成文档',
  image: '暂无生成图片',
  code: '暂无生成代码文件',
};

export function getTaskFileEmptyLabel(activeTab: TaskFileTab): string {
  return EMPTY_LABELS[activeTab];
}

export function getNextTaskFileTab(currentTab: TaskFileTab, key: TaskFileTabNavigationKey): TaskFileTab {
  const currentIndex = TASK_FILE_TABS.findIndex(tab => tab.key === currentTab);
  if (key === 'Home') return TASK_FILE_TABS[0].key;
  if (key === 'End') return TASK_FILE_TABS[TASK_FILE_TABS.length - 1].key;

  const direction = key === 'ArrowRight' ? 1 : -1;
  const nextIndex = (currentIndex + direction + TASK_FILE_TABS.length) % TASK_FILE_TABS.length;
  return TASK_FILE_TABS[nextIndex].key;
}

/** Assign every generated artifact to one, and only one, visible tab. */
export function getGeneratedTaskFileTab(artifact: TaskArtifactLike): GeneratedTaskFileTab {
  const extension = artifact.name.toLowerCase().split('.').pop() || '';

  if (artifact.type === 'image' || artifact.type === 'chart' || IMAGE_EXTENSIONS.has(extension)) {
    return 'image';
  }
  if (artifact.type === 'code' || CODE_EXTENSIONS.has(extension)) {
    return 'code';
  }
  return 'document';
}

export interface TaskFileView<TInput, TArtifact> {
  visibleInputFiles: TInput[];
  filteredArtifacts: TArtifact[];
  counts: Record<TaskFileTab, number>;
}

export function buildTaskFileView<TInput, TArtifact extends TaskArtifactLike>(
  inputFiles: readonly TInput[] | null | undefined,
  artifacts: readonly TArtifact[] | null | undefined,
  activeTab: TaskFileTab,
): TaskFileView<TInput, TArtifact> {
  const inputs = [...(inputFiles ?? [])];
  const outputs = [...(artifacts ?? [])];
  const counts: Record<TaskFileTab, number> = {
    all: inputs.length + outputs.length,
    input: inputs.length,
    document: 0,
    image: 0,
    code: 0,
  };

  for (const artifact of outputs) {
    counts[getGeneratedTaskFileTab(artifact)] += 1;
  }

  return {
    visibleInputFiles: activeTab === 'all' || activeTab === 'input' ? inputs : [],
    filteredArtifacts:
      activeTab === 'all'
        ? outputs
        : activeTab === 'input'
          ? []
          : outputs.filter(artifact => getGeneratedTaskFileTab(artifact) === activeTab),
    counts,
  };
}
