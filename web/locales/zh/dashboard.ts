import DashboardEn from '../en/dashboard';

// The dashboard namespace uses Chinese source copy as its keys.
const DashboardZh: Record<string, string> = Object.fromEntries(Object.keys(DashboardEn).map(key => [key, key]));
export default DashboardZh;
