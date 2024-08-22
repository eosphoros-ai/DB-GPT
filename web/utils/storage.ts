import { STORAGE_INIT_MESSAGE_KET, STORAGE_USERINFO_KEY } from './constants/index';

export function getInitMessage() {
  const value = localStorage.getItem(STORAGE_INIT_MESSAGE_KET) ?? '';
  try {
    const initData = JSON.parse(value) as { id: string; message: string };
    return initData;
  } catch (e) {
    return null;
  }
}

export function getUserId(): string | undefined {
  try {
    const id = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '')['user_id'];
    return id;
  } catch (e) {
    return undefined;
  }
}
