"use client"
import { useRequest } from 'ahooks';
import { sendGetRequest, sendPostRequest } from '@/utils/request';
import useAgentChat from '@/hooks/useAgentChat';
import ChatBoxComp from '@/components/chatBox';
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
		queryAgentURL: `http://30.183.153.109:5000/v1/chat/completions`,
		queryBody: {
			conv_uid: props.params?.agentId,
			chat_mode: props.searchParams?.scene || 'chat_normal',
		},
		initHistory: historyList?.data
	});

	return (
		<div className='mx-auto flex h-full max-w-3xl flex-col gap-6 px-5 py-6 sm:gap-8 xl:max-w-5xl '>
			<ChatBoxComp
				initialMessage={historyList?.data ? (historyList?.data?.length <= 0 ? props.searchParams?.initMessage : undefined) : undefined}
				clearIntialMessage={async () => {
					await refreshDialogList();
				}}
				messages={history || []}
				onSubmit={handleChatSubmit}
				paramsList={paramsList?.data}
			/>
		</div>
	)
}

export default AgentPage;