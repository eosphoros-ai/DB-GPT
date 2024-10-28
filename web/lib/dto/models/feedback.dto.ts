import { DataTypes } from 'sequelize';
import { sequelize } from '../connect';

export interface FeedbackModal {
  id: number;
  content: string;
  imgUrl: string;
}

const FeedbackDTO = sequelize.define('feedback', {
  id: {
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true,
  },
  content: DataTypes.STRING(1000),
  imgUrl: DataTypes.STRING(100),
});

export default FeedbackDTO;
