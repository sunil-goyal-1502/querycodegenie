
import React from 'react';
import { User, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';

export type ChatMessageType = {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  isLoading?: boolean;
  relevantFiles?: string[];
};

type ChatMessageProps = {
  message: ChatMessageType;
  onFileClick?: (filePath: string) => void;
  className?: string;
};

export default function ChatMessage({ message, onFileClick, className }: ChatMessageProps) {
  const { toast } = useToast();

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    toast({
      description: "Copied to clipboard",
    });
  };

  // Simple markdown-like formatting
  const formatContent = (content: string) => {
    let formatted = content;

    // Code blocks with language
    formatted = formatted.replace(
      /```(\w+)?\n([\s\S]*?)\n```/g,
      '<pre class="bg-muted p-3 my-2 rounded-md overflow-x-auto"><code class="text-sm">$2</code></pre>'
    );

    // Inline code
    formatted = formatted.replace(
      /`([^`]+)`/g,
      '<code class="bg-muted px-1.5 py-0.5 rounded text-sm">$1</code>'
    );

    // Bold
    formatted = formatted.replace(
      /\*\*([^*]+)\*\*/g,
      '<strong>$1</strong>'
    );

    // Italic
    formatted = formatted.replace(
      /\*([^*]+)\*/g,
      '<em>$1</em>'
    );

    // Unordered lists
    formatted = formatted.replace(
      /^(\s*)-\s(.+)$/gm,
      '$1• $2'
    );

    // File paths with potential highlighting
    formatted = formatted.replace(
      /\b([\w\-./]+\.(js|jsx|ts|tsx|py|java|rb|go|rs|c|cpp|h|hpp|cs|php|html|css|md))\b/g,
      '<span class="bg-primary/10 px-1 rounded">$1</span>'
    );

    // Convert newlines to <br />
    formatted = formatted.replace(/\n/g, '<br />');

    return formatted;
  };

  return (
    <div 
      className={cn(
        "px-4 py-6 flex gap-4",
        message.role === 'assistant' ? "bg-muted/50" : "bg-background",
        className
      )}
    >
      {message.role === 'user' ? (
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <User className="h-5 w-5 text-primary" />
        </div>
      ) : (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
          <Bot className="h-5 w-5 text-primary-foreground" />
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        <div className="flex items-center gap-2 mb-1">
          <div className="font-medium">{message.role === 'user' ? 'You' : 'CodeGenie'}</div>
          <div className="text-xs text-muted-foreground">
            {message.timestamp.toLocaleTimeString()}
          </div>
          {!message.isLoading && (
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-6 w-6 ml-auto" 
              onClick={handleCopy}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-3.5 w-3.5"
              >
                <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
                <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
              </svg>
            </Button>
          )}
        </div>

        {message.isLoading ? (
          <div className="flex items-center space-x-2">
            <div className="h-2 w-2 rounded-full bg-primary animate-pulse"></div>
            <div className="h-2 w-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.2s' }}></div>
            <div className="h-2 w-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.4s' }}></div>
          </div>
        ) : (
          <>
            <div 
              className="prose prose-sm dark:prose-invert max-w-none break-words"
              dangerouslySetInnerHTML={{ __html: formatContent(message.content) }}
            />
            
            {message.relevantFiles && message.relevantFiles.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-medium text-muted-foreground mb-2">Relevant Files:</div>
                <div className="flex flex-wrap gap-2">
                  {message.relevantFiles.map((file) => (
                    <Button
                      key={file}
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => onFileClick && onFileClick(file)}
                    >
                      {file.split('/').pop()}
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
