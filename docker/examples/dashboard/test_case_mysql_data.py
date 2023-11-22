import random
import string
import os
import pymysql
from typing import List

import pymysql.cursors
from datetime import datetime, timedelta

# At first you need to create an test database which called dbgpt_test;
# you can use next command to create.
# CREATE DATABASE IF NOT EXISTS dbgpt_test CHARACTER SET utf8;


def build_table(connection):
    connection.cursor().execute(
        """CREATE TABLE user (
              id INT(11) NOT NULL AUTO_INCREMENT COMMENT '用户ID',
              name VARCHAR(50) NOT NULL COMMENT '用户名',
              email VARCHAR(50) NOT NULL COMMENT '电子邮件',
              mobile CHAR(11) NOT NULL COMMENT '手机号码',
              gender VARCHAR(20) COMMENT '性别',
              birth DATE COMMENT '出生日期',
              country VARCHAR(20) COMMENT '国家',
              city VARCHAR(20) COMMENT '城市',
              create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
              PRIMARY KEY (id),
              UNIQUE KEY uk_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息表';"""
    )
    connection.cursor().execute(
        """CREATE TABLE transaction_order (
              id INT(11) NOT NULL AUTO_INCREMENT COMMENT '订单ID',
              order_no CHAR(20) NOT NULL COMMENT '订单编号',
              product_name VARCHAR(50) NOT NULL COMMENT '产品名称',
              product_category VARCHAR(20) COMMENT '产品分类',
              amount DECIMAL(10, 2) NOT NULL COMMENT '订单金额',
              pay_status VARCHAR(20) COMMENT '付款状态',
              user_id INT(11) NOT NULL COMMENT '用户ID',
              user_name VARCHAR(50) COMMENT '用户名',
              create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
              update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
              PRIMARY KEY (id),
              UNIQUE KEY uk_order_no (order_no),
              KEY idx_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易订单表';"""
    )


def user_build(names: List, country: str, grander: str = "Male") -> List:
    countries = ["China", "US", "India", "Indonesia", "Pakistan"]  # 国家列表
    cities = {
        "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou"],
        "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
        "India": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
        "Indonesia": ["Jakarta", "Surabaya", "Medan", "Bandung", "Makassar"],
        "Pakistan": ["Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Multan"],
    }

    users = []
    for i in range(1, len(names) + 1):
        if grander == "Male":
            id = int(str(countries.index(country) + 1) + "10") + i
        else:
            id = int(str(countries.index(country) + 1) + "20") + i

        name = names[i - 1]
        email = f"{name}@example.com"
        mobile = "".join(random.choices(string.digits, k=10))
        gender = grander
        birth = f"19{random.randint(60, 99)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        country = country
        city = random.choice(cities[country])

        now = datetime.now()
        year = now.year

        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        random_date = start + timedelta(days=random.randint(0, (end - start).days))
        random_time = datetime.combine(random_date, datetime.min.time()) + timedelta(
            seconds=random.randint(0, 24 * 60 * 60 - 1)
        )

        random_datetime_str = random_time.strftime("%Y-%m-%d %H:%M:%S")
        create_time = random_datetime_str
        users.append(
            (
                id,
                name,
                email,
                mobile,
                gender,
                birth,
                country,
                city,
                create_time,
                create_time,
            )
        )
    return users


def gnerate_all_users(cursor):
    users = []
    users_f = ["ZhangWei", "LiQiang", "ZhangSan", "LiSi"]
    users.extend(user_build(users_f, "China", "Male"))
    users_m = ["Hanmeimei", "LiMeiMei", "LiNa", "ZhangLi", "ZhangMing"]
    users.extend(user_build(users_m, "China", "Female"))

    users1_f = ["James", "John", "David", "Richard"]
    users.extend(user_build(users1_f, "US", "Male"))
    users1_m = ["Mary", "Patricia", "Sarah"]
    users.extend(user_build(users1_m, "US", "Female"))

    users2_f = ["Ravi", "Rajesh", "Ajay", "Arjun", "Sanjay"]
    users.extend(user_build(users2_f, "India", "Male"))
    users2_m = ["Priya", "Sushma", "Pooja", "Swati"]
    users.extend(user_build(users2_m, "India", "Female"))
    for user in users:
        cursor.execute(
            "INSERT INTO user (id, name, email, mobile, gender, birth, country, city, create_time, update_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            user,
        )

    return users


def gnerate_all_orders(users, cursor):
    orders = []
    orders_num = 200
    categories = ["Clothing", "Food", "Home Appliance", "Mother and Baby", "Travel"]

    categories_product = {
        "Clothing": ["T-shirt", "Jeans", "Skirt", "Other"],
        "Food": ["Snack", "Fruit"],
        "Home Appliance": ["Refrigerator", "Television", "Air conditioner"],
        "Mother and Baby": ["Diapers", "Milk Powder", "Stroller", "Toy"],
        "Travel": ["Tent", "Fishing Rod", "Bike", "Rawalpindi", "Multan"],
    }

    for i in range(1, orders_num + 1):
        id = i
        order_no = "".join(random.choices(string.ascii_uppercase, k=3)) + "".join(
            random.choices(string.digits, k=10)
        )
        product_category = random.choice(categories)
        product_name = random.choice(categories_product[product_category])
        amount = round(random.uniform(0, 10000), 2)
        pay_status = random.choice(["SUCCESS", "FAILD", "CANCEL", "REFUND"])
        user_id = random.choice(users)[0]
        user_name = random.choice(users)[1]

        now = datetime.now()
        year = now.year

        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        random_date = start + timedelta(days=random.randint(0, (end - start).days))
        random_time = datetime.combine(random_date, datetime.min.time()) + timedelta(
            seconds=random.randint(0, 24 * 60 * 60 - 1)
        )

        random_datetime_str = random_time.strftime("%Y-%m-%d %H:%M:%S")
        create_time = random_datetime_str

        order = (
            id,
            order_no,
            product_category,
            product_name,
            amount,
            pay_status,
            user_id,
            user_name,
            create_time,
        )
        cursor.execute(
            "INSERT INTO transaction_order (id, order_no, product_name, product_category, amount, pay_status, user_id, user_name, create_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            order,
        )


if __name__ == "__main__":
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(
            os.getenv("DB_PORT", 3306),
        ),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "aa12345678"),
        database=os.getenv("DB_DATABASE", "dbgpt_test"),
        charset="utf8mb4",
        ssl_ca=None,
    )

    build_table(connection)

    connection.commit()

    cursor = connection.cursor()

    users = gnerate_all_users(cursor)
    connection.commit()

    gnerate_all_orders(users, cursor)
    connection.commit()

    cursor.execute("SELECT * FROM user")
    data = cursor.fetchall()
    print(data)

    cursor.execute("SELECT count(*) FROM transaction_order")
    data = cursor.fetchall()
    print("orders:" + str(data))

    cursor.close()
    connection.close()
