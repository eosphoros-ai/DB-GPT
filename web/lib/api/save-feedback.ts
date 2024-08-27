import { connection } from '@/lib/dto/connect';
import FeedbackDTO, { FeedbackModal } from '../dto/models/feedback.dto';

export default async function saveFeedBack(data: Omit<FeedbackModal, 'id'>) {
  const { content, imgUrl } = data;
  try {
    await connection();
    const instance = await FeedbackDTO.create({ content, imgUrl });
    return instance.toJSON();
  } catch (e) {
    console.log('[GET USERINFO ERROR]: ', e);
    return null;
  }
}
