import { useState } from 'react';

export const useNewChat = () => {
	const [message, setMessage] = useState<string | undefined>("hello");
	
	return {
		message,
		setMessage
	};
}