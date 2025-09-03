import { ScrollArea, Stack } from '@mantine/core';
import { useEffect, useRef } from 'react';
import ChatMessage from '@/domain/ChatMessage';
import ChatMessageDisplay from '../ChatMessageDisplay/ChatMessageDisplay';
import ChatMessageLoading from '../ChatMessageLoading/ChatMessageLoading';

interface ChatWindowProps {
  messages: ChatMessage[];
  loading: boolean;
}

export default function ChatWindow({ messages, loading }: ChatWindowProps) {
  
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const viewport = viewportRef.current;
    if(viewport) {
      viewport.scrollTop = viewport.scrollHeight;
    }
  }, [messages]);

  return (
    <ScrollArea p="xs" scrollbarSize={12} style={{ height: '75vh' }} viewportRef={viewportRef}>
      <Stack>
        {messages.map((message, index) => (
          <ChatMessageDisplay key={index} message={message} />
        ))}
        {loading && <ChatMessageLoading />}
      </Stack>
    </ScrollArea>
  );
}
