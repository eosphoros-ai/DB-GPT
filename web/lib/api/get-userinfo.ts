import { connection } from '@/lib/dto/connect';
import UserDTO, { UserModel } from '@/lib/dto/models/user.dto';

export default async function getUserInfo(data: Omit<UserModel, 'id'>) {
  const { out_user_no, user_channel, avatar_url, nick_name, email, phone } = data;
  if (!out_user_no || !user_channel) return null;
  try {
    await connection();
    const userInfo = await UserDTO.findOne({ where: { out_user_no, user_channel } });
    if (userInfo) {
      return userInfo.toJSON();
    }
    const instance = await UserDTO.create({
      out_user_no,
      user_channel,
      nick_name,
      avatar_url,
      email,
      phone,
    });
    return instance.toJSON();
  } catch (e) {
    console.log('[GET USERINFO ERROR]: ', e);
    return null;
  }
}
