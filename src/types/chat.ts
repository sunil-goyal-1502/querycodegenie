export enum ChatMessageType {
  USER = 'user',
  ASSISTANT = 'assistant'
}

export interface ChatMessage {
  id: string;
  type: ChatMessageType;
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  relevantFiles?: string[];
} 