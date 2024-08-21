import { Sequelize } from 'sequelize';

export let sequelize: Sequelize;

const { MYSQL_DATABASE, MYSQL_HOST, MYSQL_PORT, MYSQL_PASSWORD, MYSQL_USERNAME } = process.env;

export async function connection() {
  if (sequelize) return;
  try {
    sequelize = new Sequelize(MYSQL_DATABASE!, MYSQL_USERNAME!, MYSQL_PASSWORD!, {
      dialect: 'mysql',
      host: MYSQL_HOST!,
      port: Number(MYSQL_PORT!),
    });
    await sequelize.authenticate();
    console.log('Connection has been established successfully.');
  } catch (e) {
    console.error('Unable to connect to the database:', e);
  }
}

connection();
