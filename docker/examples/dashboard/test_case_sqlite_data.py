import os
import random
import string
from datetime import datetime, timedelta
from typing import List
import sqlite3

# Change the database name to the desired SQLite file name.
DATABASE_NAME = "dbgpt_test.db"


def build_table(connection):
    cursor = connection.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS user (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              mobile TEXT NOT NULL,
              gender TEXT,
              birth DATE,
              country TEXT,
              city TEXT,
              create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS transaction_order (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_no TEXT NOT NULL UNIQUE,
              product_name TEXT NOT NULL,
              product_category TEXT,
              amount REAL NOT NULL,
              pay_status TEXT,
              user_id INTEGER NOT NULL,
              user_name TEXT,
              create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );"""
    )
    connection.commit()


def user_build(names: List[str], country: str, gender: str = "Male") -> List:
    countries = ["China", "US", "India", "Indonesia", "Pakistan"]
    cities = {
        "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Hangzhou"],
        "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
        "India": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
        "Indonesia": ["Jakarta", "Surabaya", "Medan", "Bandung", "Makassar"],
        "Pakistan": ["Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Multan"],
    }
    users = []
    for name in names:
        email = f"{name}@example.com"
        mobile = "".join(random.choices(string.digits, k=11))
        birth = f"19{random.randint(60, 99)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        city = random.choice(cities[country])
        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        users.append(
            (
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


def generate_all_users(cursor):
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
            "INSERT INTO user (name, email, mobile, gender, birth, country, city, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            user,
        )
    return users


def generate_all_orders(users, cursor):
    orders = []
    orders_num = 200
    categories = ["Clothing", "Food", "Home Appliance", "Mother and Baby", "Travel"]
    categories_product = {
        "Clothing": ["T-shirt", "Jeans", "Skirt", "Other"],
        "Food": ["Snack", "Fruit"],
        "Home Appliance": ["Refrigerator", "Television", "Air conditioner"],
        "Mother and Baby": ["Diapers", "Milk Powder", "Stroller", "Toy"],
        "Travel": ["Tent", "Fishing Rod", "Bike"],
    }
    for i in range(orders_num):
        id = i + 1  # Simple incremental ID
        order_no = "".join(random.choices(string.ascii_uppercase, k=3)) + "".join(
            random.choices(string.digits, k=10)
        )
        product_category = random.choice(categories)
        product_name = random.choice(categories_product[product_category])
        amount = round(random.uniform(0, 10000), 2)
        pay_status = random.choice(["SUCCESS", "FAILED", "CANCEL", "REFUND"])
        user_id = random.choice(users)[0]
        user_name = random.choice(users)[1]
        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order = (
            id,
            order_no,
            product_name,
            product_category,
            amount,
            pay_status,
            user_id,
            user_name,
            create_time,
        )
        cursor.execute(
            "INSERT INTO transaction_order (id, order_no, product_name, product_category, amount, pay_status, user_id, user_name, create_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            order,
        )


if __name__ == "__main__":
    connection = sqlite3.connect(DATABASE_NAME)
    build_table(connection)
    cursor = connection.cursor()
    users = generate_all_users(cursor)
    generate_all_orders(users, cursor)

    connection.commit()

    cursor.execute("SELECT * FROM user")
    data = cursor.fetchall()
    print(data)

    cursor.execute("SELECT COUNT(*) FROM transaction_order")
    data = cursor.fetchall()
    print("orders: " + str(data))

    cursor.close()
    connection.close()
