import { DataTypes, Model } from 'sequelize';
import { sequelize } from '../connect';

export interface UserModel {
  id: number;
  nick_name?: string;
  avatar_url?: string;
  out_user_no: string;
  user_channel: string;
  role?: string;
  email?: string;
  phone?: string;
  gmt_created?: string;
  gmt_modified?: string;
}

const UserDTO = sequelize.define<Model<UserModel, Partial<UserModel>>>(
  'User',
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    nick_name: DataTypes.STRING(100),
    out_user_no: {
      type: DataTypes.STRING(100),
      allowNull: false,
    },
    user_channel: {
      type: DataTypes.STRING(100),
      allowNull: false,
    },
    role: DataTypes.STRING(100),
    email: DataTypes.STRING(100),
    phone: DataTypes.STRING(100),
    avatar_url: DataTypes.STRING(100),
  },
  {
    tableName: 'user',
    timestamps: true,
    createdAt: 'gmt_created',
    updatedAt: 'gmt_modified',
  },
);

export default UserDTO;
