import { getIronSession, IronSession, SessionOptions } from 'iron-session';
import { GetServerSidePropsContext, GetServerSidePropsResult, NextApiHandler } from 'next';
import type { UserModel } from './dto/models/user.dto';

export interface SessionData {
  user?: UserModel;
}

export const sessionOptions: SessionOptions = {
  password: process.env.SECRET_COOKIE_PASSWORD as string,
  cookieName: 'dbgpt-portal',
  cookieOptions: {
    secure: process.env.NODE_ENV === 'production',
  },
};

/**
 * Preserve the existing Pages Router wrapper while using iron-session v8's
 * single getIronSession API. The session is attached before application code
 * runs, matching the contract of the removed v6 helper.
 */
export function withSessionRoute(handler: NextApiHandler): NextApiHandler {
  return async (req, res) => {
    req.session = await getIronSession<SessionData>(req, res, sessionOptions);
    return handler(req, res);
  };
}

export function withSessionSsr<P extends { [key: string]: unknown } = { [key: string]: unknown }>(
  handler: (context: GetServerSidePropsContext) => GetServerSidePropsResult<P> | Promise<GetServerSidePropsResult<P>>,
) {
  return async (context: GetServerSidePropsContext): Promise<GetServerSidePropsResult<P>> => {
    context.req.session = await getIronSession<SessionData>(context.req, context.res, sessionOptions);
    return handler(context);
  };
}

declare module 'http' {
  interface IncomingMessage {
    session?: IronSession<SessionData>;
  }
}
