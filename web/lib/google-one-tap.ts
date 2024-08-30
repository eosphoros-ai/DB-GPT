import { CredentialResponse, IdConfiguration } from 'google-one-tap';

export default function googleOneTap(
  { client_id, auto_select = false, cancel_on_tap_outside = false, context = 'signin' }: IdConfiguration,
  callback: (response: CredentialResponse) => void,
  otherOptions?: Omit<IdConfiguration, 'client_id'>,
) {
  const contextValue = ['signin', 'signup', 'use'].includes(context) ? context : 'signin';
  if (!client_id) {
    throw new Error('client_id is required');
  }
  if (typeof window !== 'undefined' && window.document) {
    try {
      window.google.accounts.id.initialize({
        client_id: client_id,
        callback: callback,
        auto_select: auto_select,
        cancel_on_tap_outside: cancel_on_tap_outside,
        context: contextValue,
        ...otherOptions,
      });
      window.google.accounts.id.prompt();
    } catch {
      /* empty */
    }
  }
}
