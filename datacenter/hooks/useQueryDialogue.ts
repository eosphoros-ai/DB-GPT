import { useRequest } from 'ahooks';
import { sendGetRequest } from '@/utils/request';

export function useQueryDialog() {
	const { 
		run: queryDialogueList,
		data: dialogueList,
		loading: loadingDialogList,
		refresh: refreshDialogList,
	} = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/list'), {
		manual: false,
	});

	return {
		queryDialogueList,
		dialogueList,
		loadingDialogList,
		refreshDialogList
	};
}