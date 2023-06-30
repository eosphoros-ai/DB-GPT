import { useRequest } from 'ahooks';
import { sendGetRequest } from '@/utils/request';
import { createCtx } from '@/utils/ctx-helper';
import { AxiosResponse } from 'axios';
import React from 'react';

export const [useDialogueContext, DialogueProvider] = createCtx<{
	dialogueList?: void | AxiosResponse<any, any> | undefined;
	queryDialogueList: () => void;
	refreshDialogList: () => void;
}>();

const DialogueContext = ({ children }: {
	children: React.ReactElement
}) => {
	const { 
		run: queryDialogueList,
		data: dialogueList,
		refresh: refreshDialogList,
	} = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/list'), {
		manual: true,
	});

	return (
		<DialogueProvider
			value={{
				dialogueList,
				queryDialogueList,
				refreshDialogList
			}}
		>
			{children}
		</DialogueProvider>
	)
}

export default DialogueContext;