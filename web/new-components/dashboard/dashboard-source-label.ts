export const dashboardSourceLabel = (id: string) =>
  ({
    Walmart_Sales: 'Walmart 零售数据',
    walmart_sales_demo: 'Walmart 零售数据',
    olist_ecommerce_demo: 'Olist 电商数据',
    apple_financial_demo: 'Apple 公开财报',
    sqlite_marketing_showcase: '门店营销 · 合成演示数据',
    sqlite_operations_showcase: '全国经营 · 合成演示数据',
    sqlite_healthcare_showcase: '医疗服务 · 合成演示数据',
    sqlite_rural_showcase: '普惠金融 · 合成演示数据',
    sqlite_heart_cleveland: 'UCI Cleveland · 公开研究数据',
    sqlite_voice_lab: 'AI 语音交互 · 合成演示数据',
    sqlite_itsm: 'UCI 历史服务工单',
    sqlite_energy: 'UCI 住宅实测能耗',
    sqlite_maintenance: 'UCI 合成工业样本',
    sqlite_students: 'UCI 葡语课程成绩',
    upload_001_3a6ee8a2d1ad4a2a: 'Northwind 订单数据',
  })[id] || (id.startsWith('upload_') ? '上传的数据集' : id);
