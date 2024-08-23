import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';

const useUser = () => {
  return JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '');
};

export default useUser;
