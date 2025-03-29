import { ChatEn } from '../en/chat';

type I18nKeys = keyof typeof ChatEn;

export interface Resources {
  translation: Record<I18nKeys, string>;
}

export const ChatZh: Resources['translation'] = {
  dialog_list: '对话列表',
  delete_chat: '删除会话',
  delete_chat_confirm: '您确认要删除会话吗？',
  input_tips: '可以问我任何问题，shift + Enter 换行',
  sent: '发送',
  answer_again: '重新回答',
  feedback_tip: '描述一下具体问题或更优的答案',
  thinking: '正在思考中',
  stop_replying: '停止回复',
  erase_memory: '清除记忆',
  copy_success: '复制成功',
  copy_failed: '复制失败',
  copy_nothing: '内容复制为空',
  file_tip: '文件上传后无法更改',
  chat_online: '在线对话',
  assistant: '平台小助手', // 灵数平台小助手
  model_tip: '当前应用暂不支持模型选择',
  temperature_tip: '当前应用暂不支持温度配置',
  max_new_tokens_tip: '当前应用暂不支持max_new_tokens配置',
  extend_tip: '当前应用暂不支持拓展配置',
  cot_title: '思考',
  code_preview: '预览',
  code_preview_full_screen: '全屏',
  code_preview_exit_full_screen: '退出全屏',
  code_preview_code: '代码',
  code_preview_copy: '复制',
  code_preview_already_copied: '已复制',
  code_preview_download: '下载',
  code_preview_run: '运行',
  code_preview_close: '关闭',
} as const;
