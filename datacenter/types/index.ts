import { NextApiRequest, NextPage } from 'next/types';
import { Session } from 'next-auth';

export type Message = { role: 'human' | 'ai'; context: string; createdAt?: Date };

export type AppNextApiRequest = NextApiRequest & {
    session: Session;
  };