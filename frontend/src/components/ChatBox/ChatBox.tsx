import { Button, FileInput, Group, Stack, Textarea } from '@mantine/core';
/* import {
  IconClearAll,
  IconMicrophone,
  IconMicrophoneOff,
  IconSend,
  IconUpload,
} from '@tabler/icons-react'; */
import { KeyboardEvent, useRef, useState } from 'react';
import { useReactMediaRecorder } from 'react-media-recorder-2';

interface ChatBoxProps {
  textMessageCreated: (message: string) => void;
  chatHistoryCleared: () => void;
  audioFileUploaded: (file: File | null) => void;
}

export default function ChatBox({
  textMessageCreated,
  chatHistoryCleared,
  audioFileUploaded,
}: ChatBoxProps) {
  const [message, setMessage] = useState<string>('');

  const hiddenFileInput = useRef<HTMLButtonElement>(null);
  const onAudioFileClick = () => {
    if (hiddenFileInput.current) {
      hiddenFileInput.current.click();
    }
  };

  const onNewTextMessage = () => {
    textMessageCreated(message);
    setMessage('');
  };

  const onRecordingComplete = (blobUrl: string, blob: Blob) => {
    const file = new File([blob], 'audio.wav', {
      type: blob.type,
    });

    console.log(blob);

    audioFileUploaded(file);
  };

  const { status, startRecording, stopRecording } = useReactMediaRecorder({
    audio: true,
    blobPropertyBag: {
      type: 'audio/webm',
    },
    onStop: onRecordingComplete,
  });

  const isRecording = () => status === 'recording';

  const onRecordingClick = () => {
    // Always start a new recording
    startRecording();
    
    // Create an empty audio file to trigger the API immediately
    const emptyBlob = new Blob([], { type: 'audio/webm' });
    const emptyFile = new File([emptyBlob], 'initial-audio.webm', { type: 'audio/webm' });
    audioFileUploaded(emptyFile);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if(e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onNewTextMessage();
    }
  }

  return (
    <>
      <Stack>
        <Textarea
          placeholder="Type your message here"
          autosize
          minRows={7}
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
          onKeyDown={(e) => handleKeyDown(e)}
        />
        <Group w="100%">
          <Group>
            <Button color="sccGreen.9" onClick={onNewTextMessage} /* leftSection={<IconSend />} */>
              Send
            </Button>
            <Button color="sccGreen.9" onClick={onAudioFileClick} /* leftSection={<IconUpload />} */>
              Upload Audio
            </Button>
            <Button
              /* leftSection={<IconMicrophone />} */
              onClick={onRecordingClick}
              color="sccGreen.9" 
            >
              Start Recording
            </Button>
          </Group>
          <Group ml="auto">
            <Button color="sccGreen.9" variant="outline" onClick={chatHistoryCleared} /* leftSection={<IconClearAll />} */>
              Clear Chat
            </Button>
          </Group>
        </Group>
        <FileInput
          label="Audio File"
          description="Audio File"
          placeholder="Audio File"
          style={{ display: 'none' }}
          onChange={audioFileUploaded}
          ref={hiddenFileInput}
        />
      </Stack>
    </>
  );
}