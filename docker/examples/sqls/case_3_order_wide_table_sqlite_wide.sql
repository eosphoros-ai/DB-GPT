CREATE TABLE order_wide_table (

    -- order_base
    order_id TEXT, -- 订单ID
    order_no TEXT, -- 订单编号
    parent_order_no TEXT, -- 父订单编号
    order_type INTEGER, -- 订单类型：1实物2虚拟3混合
    order_status INTEGER, -- 订单状态
    order_source TEXT, -- 订单来源
    order_source_detail TEXT, -- 订单来源详情
    create_time DATETIME, -- 创建时间
    pay_time DATETIME, -- 支付时间
    finish_time DATETIME, -- 完成时间
    close_time DATETIME, -- 关闭时间
    cancel_time DATETIME, -- 取消时间
    cancel_reason TEXT, -- 取消原因
    order_remark TEXT, -- 订单备注
    seller_remark TEXT, -- 卖家备注
    buyer_remark TEXT, -- 买家备注
    is_deleted INTEGER, -- 是否删除
    delete_time DATETIME, -- 删除时间
    order_ip TEXT, -- 下单IP
    order_platform TEXT, -- 下单平台
    order_device TEXT, -- 下单设备
    order_app_version TEXT, -- APP版本号

    -- order_amount
    currency TEXT, -- 货币类型
    exchange_rate REAL, -- 汇率
    original_amount REAL, -- 原始金额
    discount_amount REAL, -- 优惠金额
    coupon_amount REAL, -- 优惠券金额
    points_amount REAL, -- 积分抵扣金额
    shipping_amount REAL, -- 运费
    insurance_amount REAL, -- 保价费
    tax_amount REAL, -- 税费
    tariff_amount REAL, -- 关税
    payment_amount REAL, -- 实付金额
    commission_amount REAL, -- 佣金金额
    platform_fee REAL, -- 平台费用
    seller_income REAL, -- 卖家实收
    payment_currency TEXT, -- 支付货币
    payment_exchange_rate REAL, -- 支付汇率

    -- user_info
    user_id TEXT, -- 用户ID
    user_name TEXT, -- 用户名
    user_nickname TEXT, -- 用户昵称
    user_level INTEGER, -- 用户等级
    user_type INTEGER, -- 用户类型
    register_time DATETIME, -- 注册时间
    register_source TEXT, -- 注册来源
    mobile TEXT, -- 手机号
    mobile_area TEXT, -- 手机号区号
    email TEXT, -- 邮箱
    is_vip INTEGER, -- 是否VIP
    vip_level INTEGER, -- VIP等级
    vip_expire_time DATETIME, -- VIP过期时间
    user_age INTEGER, -- 用户年龄
    user_gender INTEGER, -- 用户性别
    user_birthday DATE, -- 用户生日
    user_avatar TEXT, -- 用户头像
    user_province TEXT, -- 用户所在省
    user_city TEXT, -- 用户所在市
    user_district TEXT, -- 用户所在区
    last_login_time DATETIME, -- 最后登录时间
    last_login_ip TEXT, -- 最后登录IP
    user_credit_score INTEGER, -- 用户信用分
    total_order_count INTEGER, -- 历史订单数
    total_order_amount REAL, -- 历史订单金额

    -- product_info
    product_id TEXT, -- 商品ID
    product_code TEXT, -- 商品编码
    product_name TEXT, -- 商品名称
    product_short_name TEXT, -- 商品短名称
    product_type INTEGER, -- 商品类型
    product_status INTEGER, -- 商品状态
    category_id TEXT, -- 类目ID
    category_name TEXT, -- 类目名称
    category_path TEXT, -- 类目路径
    brand_id TEXT, -- 品牌ID
    brand_name TEXT, -- 品牌名称
    brand_english_name TEXT, -- 品牌英文名
    seller_id TEXT, -- 卖家ID
    seller_name TEXT, -- 卖家名称
    seller_type INTEGER, -- 卖家类型
    shop_id TEXT, -- 店铺ID
    shop_name TEXT, -- 店铺名称
    product_price REAL, -- 商品价格
    market_price REAL, -- 市场价
    cost_price REAL, -- 成本价
    wholesale_price REAL, -- 批发价
    product_quantity INTEGER, -- 商品数量
    product_unit TEXT, -- 商品单位
    product_weight REAL, -- 商品重量(克)
    product_volume REAL, -- 商品体积(cm³)
    product_spec TEXT, -- 商品规格
    product_color TEXT, -- 商品颜色
    product_size TEXT, -- 商品尺寸
    product_material TEXT, -- 商品材质
    product_origin TEXT, -- 商品产地
    product_shelf_life INTEGER, -- 保质期(天)
    manufacture_date DATE, -- 生产日期
    expiry_date DATE, -- 过期日期
    batch_number TEXT, -- 批次号
    product_barcode TEXT, -- 商品条码
    warehouse_id TEXT, -- 发货仓库ID
    warehouse_name TEXT, -- 发货仓库名称

    -- address_info
    receiver_name TEXT, -- 收货人姓名
    receiver_mobile TEXT, -- 收货人手机
    receiver_tel TEXT, -- 收货人电话
    receiver_email TEXT, -- 收货人邮箱
    receiver_country TEXT, -- 国家
    receiver_province TEXT, -- 省份
    receiver_city TEXT, -- 城市
    receiver_district TEXT, -- 区县
    receiver_street TEXT, -- 街道
    receiver_address TEXT, -- 详细地址
    receiver_zip TEXT, -- 邮编
    address_type INTEGER, -- 地址类型
    is_default INTEGER, -- 是否默认地址
    longitude REAL, -- 经度
    latitude REAL, -- 纬度
    address_label TEXT, -- 地址标签

    -- shipping_info
    shipping_type INTEGER, -- 配送方式
    shipping_method TEXT, -- 配送方式名称
    shipping_company TEXT, -- 快递公司
    shipping_company_code TEXT, -- 快递公司编码
    shipping_no TEXT, -- 快递单号
    shipping_time DATETIME, -- 发货时间
    shipping_remark TEXT, -- 发货备注
    expect_receive_time DATETIME, -- 预计送达时间
    receive_time DATETIME, -- 收货时间
    sign_type INTEGER, -- 签收类型
    shipping_status INTEGER, -- 物流状态
    tracking_url TEXT, -- 物流跟踪URL
    is_free_shipping INTEGER, -- 是否包邮
    shipping_insurance REAL, -- 运费险金额
    shipping_distance REAL, -- 配送距离
    delivered_time DATETIME, -- 送达时间
    delivery_staff_id TEXT, -- 配送员ID
    delivery_staff_name TEXT, -- 配送员姓名
    delivery_staff_mobile TEXT, -- 配送员电话

    -- payment_info
    payment_id TEXT, -- 支付ID
    payment_no TEXT, -- 支付单号
    payment_type INTEGER, -- 支付方式
    payment_method TEXT, -- 支付方式名称
    payment_status INTEGER, -- 支付状态
    payment_platform TEXT, -- 支付平台
    transaction_id TEXT, -- 交易流水号
    payment_time DATETIME, -- 支付时间
    payment_account TEXT, -- 支付账号
    payment_bank TEXT, -- 支付银行
    payment_card_type TEXT, -- 支付卡类型
    payment_card_no TEXT, -- 支付卡号
    payment_scene TEXT, -- 支付场景
    payment_client_ip TEXT, -- 支付IP
    payment_device TEXT, -- 支付设备
    payment_remark TEXT, -- 支付备注
    payment_voucher TEXT, -- 支付凭证

    -- promotion_info
    promotion_id TEXT, -- 活动ID
    promotion_name TEXT, -- 活动名称
    promotion_type INTEGER, -- 活动类型
    promotion_desc TEXT, -- 活动描述
    promotion_start_time DATETIME, -- 活动开始时间
    promotion_end_time DATETIME, -- 活动结束时间
    coupon_id TEXT, -- 优惠券ID
    coupon_code TEXT, -- 优惠券码
    coupon_type INTEGER, -- 优惠券类型
    coupon_name TEXT, -- 优惠券名称
    coupon_desc TEXT, -- 优惠券描述
    points_used INTEGER, -- 使用积分
    points_gained INTEGER, -- 获得积分
    points_multiple REAL, -- 积分倍率
    is_first_order INTEGER, -- 是否首单
    is_new_customer INTEGER, -- 是否新客
    marketing_channel TEXT, -- 营销渠道
    marketing_source TEXT, -- 营销来源
    referral_code TEXT, -- 推荐码
    referral_user_id TEXT, -- 推荐人ID

    -- after_sale_info
    refund_id TEXT, -- 退款ID
    refund_no TEXT, -- 退款单号
    refund_type INTEGER, -- 退款类型
    refund_status INTEGER, -- 退款状态
    refund_reason TEXT, -- 退款原因
    refund_desc TEXT, -- 退款描述
    refund_time DATETIME, -- 退款时间
    refund_amount REAL, -- 退款金额
    return_shipping_no TEXT, -- 退货快递单号
    return_shipping_company TEXT, -- 退货快递公司
    return_shipping_time DATETIME, -- 退货时间
    refund_evidence TEXT, -- 退款凭证
    complaint_id TEXT, -- 投诉ID
    complaint_type INTEGER, -- 投诉类型
    complaint_status INTEGER, -- 投诉状态
    complaint_content TEXT, -- 投诉内容
    complaint_time DATETIME, -- 投诉时间
    complaint_handle_time DATETIME, -- 投诉处理时间
    complaint_handle_result TEXT, -- 投诉处理结果
    evaluation_score INTEGER, -- 评价分数
    evaluation_content TEXT, -- 评价内容
    evaluation_time DATETIME, -- 评价时间
    evaluation_reply TEXT, -- 评价回复
    evaluation_reply_time DATETIME, -- 评价回复时间
    evaluation_images TEXT, -- 评价图片
    evaluation_videos TEXT, -- 评价视频
    is_anonymous INTEGER, -- 是否匿名评价

    -- invoice_info
    invoice_type INTEGER, -- 发票类型
    invoice_title TEXT, -- 发票抬头
    invoice_content TEXT, -- 发票内容
    tax_no TEXT, -- 税号
    invoice_amount REAL, -- 发票金额
    invoice_status INTEGER, -- 发票状态
    invoice_time DATETIME, -- 开票时间
    invoice_number TEXT, -- 发票号码
    invoice_code TEXT, -- 发票代码
    company_name TEXT, -- 单位名称
    company_address TEXT, -- 单位地址
    company_tel TEXT, -- 单位电话
    company_bank TEXT, -- 开户银行
    company_account TEXT, -- 银行账号

    -- delivery_time_info
    expect_delivery_time DATETIME, -- 期望配送时间
    delivery_period_type INTEGER, -- 配送时段类型
    delivery_period_start TEXT, -- 配送时段开始
    delivery_period_end TEXT, -- 配送时段结束
    delivery_priority INTEGER, -- 配送优先级

    -- tag_info
    order_tags TEXT, -- 订单标签
    user_tags TEXT, -- 用户标签
    product_tags TEXT, -- 商品标签
    risk_level INTEGER, -- 风险等级
    risk_tags TEXT, -- 风险标签
    business_tags TEXT, -- 业务标签

    -- commercial_info
    gross_profit REAL, -- 毛利
    gross_profit_rate REAL, -- 毛利率
    settlement_amount REAL, -- 结算金额
    settlement_time DATETIME, -- 结算时间
    settlement_cycle INTEGER, -- 结算周期
    settlement_status INTEGER, -- 结算状态
    commission_rate REAL, -- 佣金比例
    platform_service_fee REAL, -- 平台服务费
    ad_cost REAL, -- 广告费用
    promotion_cost REAL -- 推广费用
);

-- 插入示例数据
INSERT INTO order_wide_table (
    -- 基础订单信息
    order_id, order_no, order_type, order_status, create_time, order_source,
    -- 订单金额
    original_amount, payment_amount, shipping_amount,
    -- 用户信息
    user_id, user_name, user_level, mobile,
    -- 商品信息
    product_id, product_name, product_quantity, product_price,
    -- 收货信息
    receiver_name, receiver_mobile, receiver_address,
    -- 物流信息
    shipping_no, shipping_status,
    -- 支付信息
    payment_type, payment_status,
    -- 营销信息
    promotion_id, coupon_amount,
    -- 发票信息
    invoice_type, invoice_title
) VALUES 
(
    'ORD20240101001', 'NO20240101001', 1, 2, '2024-01-01 10:00:00', 'APP',
    199.99, 188.88, 10.00,
    'USER001', '张三', 2, '13800138000',
    'PRD001', 'iPhone 15 手机壳', 2, 89.99,
    '李四', '13900139000', '北京市朝阳区XX路XX号',
    'SF123456789', 1,
    1, 1,
    'PROM001', 20.00,
    1, '个人'
),
(
    'ORD20240101002', 'NO20240101002', 1, 1, '2024-01-01 11:00:00', 'H5',
    299.99, 279.99, 0.00,
    'USER002', '王五', 3, '13700137000',
    'PRD002', 'AirPods Pro 保护套', 1, 299.99,
    '赵六', '13600136000', '上海市浦东新区XX路XX号',
    'YT987654321', 2,
    2, 2,
    'PROM002', 10.00,
    2, '上海科技有限公司'
),
(
    'ORD20240101003', 'NO20240101003', 2, 3, '2024-01-01 12:00:00', 'WEB',
    1999.99, 1899.99, 0.00,
    'USER003', '陈七', 4, '13500135000',
    'PRD003', 'MacBook Pro 电脑包', 1, 1999.99,
    '孙八', '13400134000', '广州市天河区XX路XX号',
    'JD123123123', 3,
    3, 1,
    'PROM003', 100.00,
    1, '个人'
);
