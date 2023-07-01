"use client"
import { useRequest } from 'ahooks';
import { sendGetRequest, sendPostRequest } from '@/utils/request';
import useAgentChat from '@/hooks/useAgentChat';
import ChatBoxComp from '@/components/chatBoxTemp';
import { useDialogueContext } from '@/app/context/dialogue';

const AgentPage = (props: {
	params: {
		agentId?: string;
	},
	searchParams: {
		scene?: string;
		initMessage?: string;
	}
}) => {
	const { refreshDialogList } = useDialogueContext();

	const { data: historyList } = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/messages/history', {
		con_uid: props.params?.agentId
	}), {
		ready: !!props.params?.agentId
	});

	const { data: paramsList } = useRequest(async () => await sendPostRequest(`/v1/chat/mode/params/list?chat_mode=${props.searchParams?.scene}`), {
		ready: !!props.searchParams?.scene
	});

	const { history, handleChatSubmit } = useAgentChat({
		queryAgentURL: `/v1/chat/completions`,
		queryBody: {
			conv_uid: props.params?.agentId,
			chat_mode: props.searchParams?.scene || 'chat_normal',
		},
		initHistory: historyList?.data
	});

	return (
		<>
			<ChatBoxComp
				initialMessage={historyList?.data ? (historyList?.data?.length <= 0 ? props.searchParams?.initMessage : undefined) : undefined}
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