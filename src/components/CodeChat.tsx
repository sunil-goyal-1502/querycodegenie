
import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Send, CornerDownLeft } from 'lucide-react';
import ChatMessage, { ChatMessageType } from './ChatMessage';
import { CodeIndicesService } from '@/utils/codeIndicesService';
import { useToast } from '@/components/ui/use-toast';
import { v4 as uuidv4 } from 'uuid';

type CodeChatProps = {
  onFileSelect?: (filePath: string) => void;
  className?: string;
};

export function CodeChat({ onFileSelect, className }: CodeChatProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;
    
    // Add user message
    const userMessage: ChatMessageType = {
      id: uuidv4(),
      content: input,
      role: 'user',
      timestamp: new Date(),
    };
    
    // Add loading message for assistant
    const assistantLoadingMessage: ChatMessageType = {
      id: uuidv4(),
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isLoading: true,
    };
    
    setMessages(messages => [...messages, userMessage, assistantLoadingMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Try to query the codebase with streaming response
      const stream = await CodeIndicesService.queryCode(input, true) as ReadableStream;
      
      if (!stream) {
        throw new Error("Failed to get response stream");
      }
      
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let responseText = '';
      let relevantFiles: string[] = [];
      
      // Process the streamed response
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              
              if (data.chunk) {
                responseText += data.chunk;
                
                // Update the message with the current accumulated response
                setMessages(messages => 
                  messages.map(msg => 
                    msg.id === assistantLoadingMessage.id
                      ? { ...msg, content: responseText, isLoading: false }
                      : msg
                  )
                );
              } else if (data.error) {
                throw new Error(data.error);
              } else if (data.done) {
                // Handle completion if needed
              }
            } catch (e) {
              console.error("Error parsing SSE data:", e);
            }
          }
        }
      }
      
      // Get relevant files after the streamed response is complete
      const fullResponse = await CodeIndicesService.queryCode(input);
      
      if (typeof fullResponse !== 'object' || !fullResponse) {
        throw new Error("Invalid response format");
      }
      
      const typedResponse = fullResponse as { success: boolean; relevant_files?: string[] };
      
      if (typedResponse.success && typedResponse.relevant_files) {
        relevantFiles = typedResponse.relevant_files;
        
        // Update the message with relevant files
        setMessages(messages => 
          messages.map(msg => 
            msg.id === assistantLoadingMessage.id
              ? { ...msg, relevantFiles }
              : msg
          )
        );
      }
    } catch (error) {
      console.error("Error querying code:", error);
      
      // Update the loading message with error information
      setMessages(messages => 
        messages.map(msg => 
          msg.id === assistantLoadingMessage.id
            ? { 
                ...msg, 
                content: `Sorry, I couldn't process your request. ${error instanceof Error ? error.message : "An unknown error occurred."}`, 
                isLoading: false 
              }
            : msg
        )
      );
      
      toast({
        title: "Query Error",
        description: error instanceof Error ? error.message : "Failed to query the codebase",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <ScrollArea className="flex-1 p-0">
        <div className="flex flex-col divide-y">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center p-4">
              <div className="rounded-full bg-primary/10 p-3 mb-4">
                <svg 
                  width="24" 
                  height="24" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2" 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  className="text-primary h-6 w-6"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </div>
              <h3 className="font-medium text-lg mb-2">Ask questions about your code</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                After indexing your code, you can ask questions like "How does the user authentication flow work?" or 
                "What files are responsible for handling API requests?"
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessage 
                key={message.id} 
                message={message} 
                onFileClick={onFileSelect}
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>
      
      <div className="p-4 border-t">
        <div className="flex space-x-2">
          <Input
            placeholder="Ask about your code..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            className="flex-1"
          />
          <Button 
            onClick={handleSendMessage} 
            disabled={!input.trim() || isLoading}
            size="icon"
          >
            {isLoading ? (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>
        <div className="flex justify-end mt-2">
          <div className="text-xs text-muted-foreground flex items-center">
            Press <kbd className="px-1.5 py-0.5 bg-muted border rounded text-xs mx-1 inline-flex items-center"><CornerDownLeft className="h-3 w-3" /></kbd> to send
          </div>
        </div>
      </div>
    </div>
  );
}

export default CodeChat;
