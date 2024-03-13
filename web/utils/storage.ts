import { STORAGE_INIT_MESSAGE_KET } from '@/utils';

export function getInitMessage() {
  const value = localStorage.getItem(STORAGE_INIT_MESSAGE_KET) ?? '';
  try {
    const initData = JSON.parse(value) as { id: string; message: string };
    return initData;
  } catch (e) {
    return null;
  }
}
