import { STORAGE_INIT_MESSAGE_KET, STORAGE_USERINFO_KEY } from './constants/index';

export function getInitMessage() {
  const value = localStorage.getItem(STORAGE_INIT_MESSAGE_KET) ?? '';
  try {
    const initData = JSON.parse(value) as { id: string; message: string };
    return initData;
  } catch {
    return null;
  }
}

export function getUserId(): string | undefined {
  try {
    const user = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '');
    return user?.user_id || user?.user_no || undefined;
  } catch {
    return undefined;
  }
}
