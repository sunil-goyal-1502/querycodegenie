import { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";
import { Send, CornerDownLeft } from "lucide-react";
import { ChatMessage, ChatMessageType } from '@/types/chat';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';

// Base URL for API
const API_BASE_URL = "http://localhost:5001/api";

interface FileMethod {
  name: string;
  type: string;
  summary: string;
}

interface FileInfo {
  summary: string;
  type: string;
  is_entry_point: boolean;
  is_core_file: boolean;
  methods: FileMethod[];
}

interface RelevantFiles {
  [key: string]: FileInfo;
}

export default function CodeChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [relevantFiles, setRelevantFiles] = useState<RelevantFiles>({});
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const { toast } = useToast();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    // Add user message
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      type: ChatMessageType.USER,
      content: input,
      timestamp: new Date(),
      isLoading: false
    }]);

    // Add assistant message placeholder
    setMessages(prev => [...prev, {
      id: (Date.now() + 1).toString(),
      type: ChatMessageType.ASSISTANT,
      content: "",
      timestamp: new Date(),
      isLoading: true
    }]);

    setIsLoading(true);
    setInput("");

    try {
      const eventSource = new EventSource(
        `${API_BASE_URL}/query?query=${encodeURIComponent(input)}&stream=true`
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.relevant_files) {
            setRelevantFiles(data.relevant_files);
          } else if (data.chunk) {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              if (lastMessage.type === ChatMessageType.ASSISTANT) {
                lastMessage.content += data.chunk;
                lastMessage.isLoading = false;
              }
              return newMessages;
            });
          } else if (data.error) {
            toast({
              title: "Error",
              description: data.error,
              variant: "destructive",
            });
            setIsLoading(false);
          } else if (data.done) {
            setIsLoading(false);
          }
        } catch (error) {
          console.error('Error parsing message:', error);
          toast({
            title: "Error",
            description: "Failed to parse server response",
            variant: "destructive",
          });
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        setIsLoading(false);
        toast({
          title: "Error",
          description: "Failed to get response from server. Please try again.",
          variant: "destructive",
        });
      };

      eventSource.addEventListener('done', () => {
        eventSource.close();
        setIsLoading(false);
      });
    } catch (error) {
      console.error('Error:', error);
      setIsLoading(false);
      toast({
        title: "Error",
        description: "Failed to send message. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-hidden">
        <ScrollArea ref={scrollAreaRef} className="h-full p-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`mb-4 ${
                message.type === ChatMessageType.USER ? 'text-right' : 'text-left'
              }`}
            >
              <div
                className={`inline-block max-w-[80%] p-4 rounded-lg ${
                  message.type === ChatMessageType.USER
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                <pre className="whitespace-pre-wrap break-words font-sans">
                  {message.content}
                </pre>
              </div>
            </div>
          ))}
          {Object.keys(relevantFiles).length > 0 && (
            <Card className="mb-4">
              <CardHeader>
                <CardTitle>Relevant Files</CardTitle>
                <CardDescription>
                  Files that are most relevant to your query
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="single" collapsible>
                  {Object.entries(relevantFiles).map(([filePath, info]) => (
                    <AccordionItem key={filePath} value={filePath}>
                      <AccordionTrigger>
                        <div className="flex items-center gap-2">
                          <span>{filePath}</span>
                          {info.is_entry_point && (
                            <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                              Entry Point
                            </span>
                          )}
                          {info.is_core_file && (
                            <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded">
                              Core File
                            </span>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold">Summary</h4>
                            <p>{info.summary}</p>
                          </div>
                          {info.methods.length > 0 && (
                            <div>
                              <h4 className="font-semibold">Methods</h4>
                              <ul className="list-disc list-inside space-y-2">
                                {info.methods.map((method) => (
                                  <li key={method.name}>
                                    <span className="font-mono">{method.name}</span>
                                    <span className="text-sm text-muted-foreground">
                                      {' '}
                                      - {method.summary}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </CardContent>
            </Card>
          )}
          {suggestions.length > 0 && (
            <Card className="mb-4">
              <CardHeader>
                <CardTitle>Suggested Questions</CardTitle>
                <CardDescription>
                  You might want to ask about these aspects
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="list-disc list-inside space-y-2">
                  {suggestions.map((suggestion, index) => (
                    <li
                      key={index}
                      className="cursor-pointer hover:text-primary"
                      onClick={() => {
                        setInput(suggestion.replace(/^- /, ''));
                      }}
                    >
                      {suggestion}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </ScrollArea>
      </div>
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <Input
            placeholder="Ask about the codebase..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <Button
            onClick={handleSendMessage}
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? (
              <CornerDownLeft className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
