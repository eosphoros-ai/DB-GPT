CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    user_name VARCHAR(100),
    user_email VARCHAR(100),
    registration_date DATE,
    user_country VARCHAR(100)
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(100),
    product_price REAL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    order_date DATE,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

INSERT INTO users (user_id, user_name, user_email, registration_date, user_country) VALUES
(1, 'John', 'john@gmail.com', '2020-01-01', 'USA'),
(2, 'Mary', 'mary@gmail.com', '2021-01-01', 'UK'),
(3, 'Bob', 'bob@gmail.com', '2020-01-01', 'USA'),
(4, 'Alice', 'alice@gmail.com', '2021-01-01', 'UK'),
(5, 'Charlie', 'charlie@gmail.com', '2020-01-01', 'USA'),
(6, 'David', 'david@gmail.com', '2021-01-01', 'UK'),
(7, 'Eve', 'eve@gmail.com', '2020-01-01', 'USA'),
(8, 'Frank', 'frank@gmail.com', '2021-01-01', 'UK'),
(9, 'Grace', 'grace@gmail.com', '2020-01-01', 'USA'),
(10, 'Helen', 'helen@gmail.com', '2021-01-01', 'UK');

INSERT INTO products (product_id, product_name, product_price) VALUES
(1, 'iPhone', 699),
(2, 'Samsung Galaxy', 599),
(3, 'iPad', 329),
(4, 'Macbook', 1299),
(5, 'Apple Watch', 399),
(6, 'AirPods', 159),
(7, 'Echo', 99),
(8, 'Kindle', 89),
(9, 'Fire TV Stick', 39),
(10, 'Echo Dot', 49);

INSERT INTO orders (order_id, user_id, product_id, quantity, order_date) VALUES
(1, 1, 1, 1, '2022-01-01'),
(2, 1, 2, 1, '2022-02-01'),
(3, 2, 3, 2, '2022-03-01'),
(4, 2, 4, 1, '2022-04-01'),
(5, 3, 5, 2, '2022-05-01'),
(6, 3, 6, 3, '2022-06-01'),
(7, 4, 7, 2, '2022-07-01'),
(8, 4, 8, 1, '2022-08-01'),
(9, 5, 9, 2, '2022-09-01'),
(10, 5, 10, 3, '2022-10-01');
