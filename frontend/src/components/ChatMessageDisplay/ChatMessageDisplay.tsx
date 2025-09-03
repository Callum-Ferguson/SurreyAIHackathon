import { Card, Flex } from '@mantine/core';
import ChatMessage from '@/domain/ChatMessage';

interface ChatMessageDisplayProps {
  message: ChatMessage;
}

export default function ChatMessageDisplay({ message }: ChatMessageDisplayProps) {
  const justify = message.role === 'bot' ? 'flex-start' : 'flex-end';
  let bg = message.role === 'bot' ? 'gray.2' : 'sccGreen.9';

  let c = message.role === 'bot' ? 'black' : 'white';

  if (message.type === 'error') {
    bg = 'sccRed.9';
    c = 'white';
  }

  return (
    <Flex justify={justify}>
      <Card bg={bg} w="55%" c={c} shadow="none">
        {message.message}
      </Card>
    </Flex>
  );
}
