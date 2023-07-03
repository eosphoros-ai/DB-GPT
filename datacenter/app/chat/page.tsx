"use client"
import { useRequest } from 'ahooks';
import { sendGetRequest, sendPostRequest } from '@/utils/request';
import useAgentChat from '@/hooks/useAgentChat';
import ChatBoxComp from '@/components/chatBoxTemp';
import { useDialogueContext } from '@/app/context/dialogue';
import { useSearchParams } from 'next/navigation';

const AgentPage = () => {
	const searchParams = useSearchParams();
	const { refreshDialogList } = useDialogueContext();
	const id = searchParams.get('id');
	const scene = searchParams.get('scene');

	const { data: historyList } = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/messages/history', {
		con_uid: id
	}), {
		ready: !!id,
		refreshDeps: [id]
	});

	const { data: paramsList } = useRequest(async () => await sendPostRequest(`/v1/chat/mode/params/list?chat_mode=${scene}`), {
		ready: !!scene,
		refreshDeps: [id, scene]
	});

	const { history, handleChatSubmit } = useAgentChat({
		queryAgentURL: `/v1/chat/completions`,
		queryBody: {
			conv_uid: id,
			chat_mode: scene || 'chat_normal',
		},
		initHistory: historyList?.data
	});

	return (
		<>
			<ChatBoxComp
				clearIntialMessage={async () => {
					await refreshDialogList();
				}}
				messages={history || []}
				onSubmit={handleChatSubmit}
				paramsList={paramsList?.data}
			/>
		</>
	)
}

export default AgentPage;