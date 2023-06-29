"use client"
import { useRequest } from 'ahooks';
import { sendGetRequest } from '@/utils/request';
import useAgentChat from '@/hooks/useAgentChat';
import ChatBoxComp from '@/components/chatBox';

const AgentPage = (props) => {
	const { data: historyList } = useRequest(async () => await sendGetRequest('/v1/chat/dialogue/messages/history', {
		con_uid: props.params?.agentId
	}), {
		ready: !!props.params?.agentId
	});

	const { history, handleChatSubmit } = useAgentChat({
		queryAgentURL: `http://30.183.154.8:5000/v1/chat/completions`,
		queryBody: {
			conv_uid: props.params?.agentId,
			chat_mode: 'chat_normal'
		},
		initHistory: historyList?.data
	});

	return (
		<div className='mx-auto flex h-full max-w-3xl flex-col gap-6 px-5 pt-6 sm:gap-8 xl:max-w-4xl'>
			<ChatBoxComp
				initialMessage={historyList?.data ? (historyList?.data?.length <= 0 ? props.searchParams?.initMessage : undefined) : undefined}
				clearIntialMessage={() => {
					const searchParams = new URLSearchParams(window.location.search);
					searchParams.delete('initMessage');
					window.history.replaceState(null, null, `?${searchParams.toString()}`);
				}}
				messages={history || []}
				onSubmit={handleChatSubmit}
			/>
		</div>
	)
}
export default AgentPage;