import { NextApiRequest, NextPage } from 'next/types';
import { Session } from 'next-auth';

export type Message = { from: 'human' | 'agent'; message: string; createdAt?: Date };

export type AppNextApiRequest = NextApiRequest & {
    session: Session;
  };