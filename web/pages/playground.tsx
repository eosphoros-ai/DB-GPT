import { ChatPage, ChatTurn, ContentPart, SlashCommand } from '@/new-components/chat';
import React, { useCallback, useRef, useState } from 'react';

const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

const demoCommands: SlashCommand[] = [
  { id: 'clear', trigger: 'clear', title: 'Clear History', description: 'Clear all chat history', type: 'builtin' },
  { id: 'model', trigger: 'model', title: 'Switch Model', description: 'Change the AI model', type: 'builtin' },
  { id: 'help', trigger: 'help', title: 'Help', description: 'Show available commands', type: 'builtin' },
  {
    id: 'export',
    trigger: 'export',
    title: 'Export Chat',
    description: 'Export conversation as file',
    type: 'builtin',
  },
];

const demoAgents = [
  { name: 'SQL Expert', description: 'Database query and optimization specialist' },
  { name: 'Code Assistant', description: 'Help with coding tasks' },
  { name: 'Data Analyst', description: 'Data analysis and visualization' },
];

const PlaygroundPage: React.FC = () => {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const simulateResponse = useCallback(async (userMessage: string): Promise<string> => {
    await new Promise(resolve => setTimeout(resolve, 500));

    const responses = [
      `I understand you're asking about "${userMessage.slice(0, 30)}...". Let me help you with that.\n\nHere's a detailed response:\n\n1. First, let's analyze the problem\n2. Then, we'll explore possible solutions\n3. Finally, I'll provide recommendations\n\nWould you like me to elaborate on any of these points?`,
      `Great question! Based on my analysis:\n\n**Key Points:**\n- The approach you're considering is valid\n- However, there are some considerations\n- Let me explain the trade-offs\n\n\`\`\`sql\nSELECT * FROM users WHERE status = 'active';\n\`\`\`\n\nThis query demonstrates the concept.`,
      `I've analyzed your request and here's what I found:\n\n| Metric | Value | Status |\n|--------|-------|--------|\n| Performance | 95% | ✅ Good |\n| Reliability | 99.9% | ✅ Excellent |\n| Cost | $0.05 | ✅ Low |\n\nOverall, the results look promising!`,
    ];

    return responses[Math.floor(Math.random() * responses.length)];
  }, []);

  const handleSendMessage = useCallback(
    async (text: string, _parts: ContentPart[]) => {
      const turnId = generateId();
      const startTime = Date.now();

      abortControllerRef.current = new AbortController();

      const newTurn: ChatTurn = {
        id: turnId,
        userMessage: text,
        isWorking: true,
        startTime,
        steps: [{ id: '1', name: 'Processing request', status: 'running', tool: 'read', startTime }],
      };

      setTurns(prev => [...prev, newTurn]);
      setIsGenerating(true);

      try {
        await new Promise(resolve => setTimeout(resolve, 800));

        if (abortControllerRef.current?.signal.aborted) return;

        setTurns(prev =>
          prev.map(t =>
            t.id === turnId
              ? {
                  ...t,
                  steps: [
                    {
                      id: '1',
                      name: 'Processing request',
                      status: 'completed',
                      tool: 'read',
                      startTime,
                      endTime: Date.now(),
                    },
                    { id: '2', name: 'Generating response', status: 'running', tool: 'code', startTime: Date.now() },
                  ],
                }
              : t,
          ),
        );

        const response = await simulateResponse(text);

        if (abortControllerRef.current?.signal.aborted) return;

        const endTime = Date.now();

        setTurns(prev =>
          prev.map(t =>
            t.id === turnId
              ? {
                  ...t,
                  assistantMessage: response,
                  isWorking: false,
                  endTime,
                  steps: [
                    {
                      id: '1',
                      name: 'Processing request',
                      status: 'completed',
                      tool: 'read',
                      startTime,
                      endTime: startTime + 800,
                    },
                    {
                      id: '2',
                      name: 'Generating response',
                      status: 'completed',
                      tool: 'code',
                      startTime: startTime + 800,
                      endTime,
                    },
                  ],
                }
              : t,
          ),
        );
      } catch (error) {
        console.error('Error generating response:', error);

        setTurns(prev =>
          prev.map(t =>
            t.id === turnId
              ? {
                  ...t,
                  assistantMessage: 'Sorry, an error occurred while generating the response.',
                  isWorking: false,
                  endTime: Date.now(),
                  steps: t.steps?.map(s => ({ ...s, status: 'failed' as const })),
                }
              : t,
          ),
        );
      } finally {
        setIsGenerating(false);
        abortControllerRef.current = null;
      }
    },
    [simulateResponse],
  );

  const handleStopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsGenerating(false);

      setTurns(prev =>
        prev.map(t =>
          t.isWorking
            ? {
                ...t,
                isWorking: false,
                endTime: Date.now(),
                assistantMessage: t.assistantMessage || 'Generation stopped by user.',
                steps: t.steps?.map(s =>
                  s.status === 'running' ? { ...s, status: 'failed' as const, error: 'Cancelled' } : s,
                ),
              }
            : t,
        ),
      );
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setTurns([]);
  }, []);

  const handleCommandSelect = useCallback((command: SlashCommand) => {
    if (command.trigger === 'clear') {
      setTurns([]);
    } else {
      console.log('Command selected:', command);
    }
  }, []);

  const handleFileSearch = useCallback(async (query: string): Promise<string[]> => {
    await new Promise(resolve => setTimeout(resolve, 200));

    const mockFiles = [
      'src/components/Button.tsx',
      'src/components/Input.tsx',
      'src/pages/index.tsx',
      'src/utils/helpers.ts',
      'package.json',
      'tsconfig.json',
    ];

    return mockFiles.filter(f => f.toLowerCase().includes(query.toLowerCase()));
  }, []);

  return (
    <div className='h-screen'>
      <ChatPage
        turns={turns}
        isLoading={isGenerating}
        modelName='GPT-4'
        title='中涣信息 Playground'
        onSendMessage={handleSendMessage}
        onStopGeneration={handleStopGeneration}
        onNewChat={handleNewChat}
        agents={demoAgents}
        commands={demoCommands}
        onCommandSelect={handleCommandSelect}
        onFileSearch={handleFileSearch}
        showSteps={true}
        inputPlaceholder='Ask me anything... (try @ for mentions, / for commands)'
      />
    </div>
  );
};

export default PlaygroundPage;
