import { NextApiRequest, NextPage } from 'next/types';
import { Session } from 'next-auth';

export type Message = { role: 'human' | 'view'; context: string; createdAt?: Date };

export type AppNextApiRequest = NextApiRequest & {
  session: Session;
};

export interface DialogueItem {
  chat_mode: string;
  conv_uid: string;
  select_param?: string;
  user_input?: string;
  user_name?: string;
}