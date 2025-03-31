
import React, { useState, useEffect } from 'react';
import { Code2, Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

type CodeViewerProps = {
  content: string;
  language: string;
  filePath: string;
  className?: string;
};

export function CodeViewer({ content, language, filePath, className }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [highlightedContent, setHighlightedContent] = useState<JSX.Element>(
    <pre>{content}</pre>
  );

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Simple language-based formatting for languages we can detect
  useEffect(() => {
    // Very basic syntax highlighting (just for display purposes)
    if (language === 'javascript' || language === 'typescript') {
      const formattedContent = formatJsTs(content);
      setHighlightedContent(formattedContent);
    } else if (language === 'python') {
      const formattedContent = formatPython(content);
      setHighlightedContent(formattedContent);
    } else if (language === 'html' || language === 'xml') {
      const formattedContent = formatHtml(content);
      setHighlightedContent(formattedContent);
    } else if (language === 'css' || language === 'scss') {
      const formattedContent = formatCss(content);
      setHighlightedContent(formattedContent);
    } else {
      // For other languages, just wrap in a pre tag
      setHighlightedContent(<pre className="whitespace-pre-wrap">{content}</pre>);
    }
  }, [content, language]);

  return (
    <div className={cn("rounded-md border bg-card", className)}>
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <div className="flex items-center gap-2 truncate">
          <Code2 className="h-4 w-4" />
          <span className="text-sm font-medium truncate">{filePath}</span>
        </div>
        <div className="flex gap-2 items-center">
          <Badge variant="outline" className="text-xs">
            {language}
          </Badge>
          <Button variant="ghost" size="icon" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </div>
      <Tabs defaultValue="code" className="w-full">
        <div className="px-4 border-b">
          <TabsList className="h-9">
            <TabsTrigger value="code" className="text-xs">Code</TabsTrigger>
            <TabsTrigger value="raw" className="text-xs">Raw</TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="code" className="mt-0 p-0">
          <ScrollArea className="h-[calc(100vh-15rem)] max-h-[50vh]">
            <div className="p-4 font-mono text-sm">
              {highlightedContent}
            </div>
          </ScrollArea>
        </TabsContent>
        
        <TabsContent value="raw" className="mt-0 p-0">
          <ScrollArea className="h-[calc(100vh-15rem)] max-h-[50vh]">
            <pre className="p-4 font-mono text-sm whitespace-pre-wrap">
              {content}
            </pre>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Very basic syntax highlighting functions
function formatJsTs(code: string): JSX.Element {
  const keywords = ['const', 'let', 'var', 'function', 'class', 'import', 'export', 'from', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch', 'finally', 'throw', 'new', 'this', 'super', 'extends', 'implements', 'static', 'public', 'private', 'protected', 'interface', 'type', 'enum'];
  
  // Split the code by tokens we want to highlight
  const lines = code.split('\n');
  
  return (
    <div>
      {lines.map((line, lineIndex) => {
        // Basic token highlighting - keywords, strings, comments
        let formattedLine = line;
        
        // Comments
        formattedLine = formattedLine.replace(
          /(\/\/.*$|\/\*[\s\S]*?\*\/)/g,
          '<span style="color: #6a9955;">$1</span>'
        );
        
        // Strings
        formattedLine = formattedLine.replace(
          /(['"])(\\(?:\r\n|[\s\S])|(?!\1)[^\\\r\n])*\1/g,
          '<span style="color: #ce9178;">$&</span>'
        );
        
        // Keywords
        keywords.forEach(keyword => {
          const regex = new RegExp(`\\b${keyword}\\b`, 'g');
          formattedLine = formattedLine.replace(
            regex,
            `<span style="color: #569cd6;">$&</span>`
          );
        });
        
        // Replace spaces with non-breaking spaces to preserve indentation
        formattedLine = formattedLine.replace(/^ +/g, match => {
          return '&nbsp;'.repeat(match.length);
        });
        
        return (
          <div 
            key={lineIndex} 
            className="whitespace-pre" 
            dangerouslySetInnerHTML={{ __html: formattedLine || '&nbsp;' }} 
          />
        );
      })}
    </div>
  );
}

function formatPython(code: string): JSX.Element {
  const keywords = ['def', 'class', 'import', 'from', 'as', 'return', 'if', 'elif', 'else', 'for', 'while', 'break', 'continue', 'try', 'except', 'finally', 'with', 'raise', 'pass', 'lambda', 'None', 'True', 'False', 'and', 'or', 'not', 'in', 'is', 'global', 'nonlocal', 'assert', 'async', 'await', 'yield'];
  
  // Split the code by tokens we want to highlight
  const lines = code.split('\n');
  
  return (
    <div>
      {lines.map((line, lineIndex) => {
        // Basic token highlighting - keywords, strings, comments
        let formattedLine = line;
        
        // Comments
        formattedLine = formattedLine.replace(
          /(#.*$)/g,
          '<span style="color: #6a9955;">$1</span>'
        );
        
        // Strings
        formattedLine = formattedLine.replace(
          /(['"])(\\(?:\r\n|[\s\S])|(?!\1)[^\\\r\n])*\1/g,
          '<span style="color: #ce9178;">$&</span>'
        );
        
        // Keywords
        keywords.forEach(keyword => {
          const regex = new RegExp(`\\b${keyword}\\b`, 'g');
          formattedLine = formattedLine.replace(
            regex,
            `<span style="color: #569cd6;">$&</span>`
          );
        });
        
        // Replace spaces with non-breaking spaces to preserve indentation
        formattedLine = formattedLine.replace(/^ +/g, match => {
          return '&nbsp;'.repeat(match.length);
        });
        
        return (
          <div 
            key={lineIndex} 
            className="whitespace-pre" 
            dangerouslySetInnerHTML={{ __html: formattedLine || '&nbsp;' }} 
          />
        );
      })}
    </div>
  );
}

function formatHtml(code: string): JSX.Element {
  // Split the code by tokens we want to highlight
  const lines = code.split('\n');
  
  return (
    <div>
      {lines.map((line, lineIndex) => {
        // Basic token highlighting for HTML
        let formattedLine = line;
        
        // Tags
        formattedLine = formattedLine.replace(
          /(&lt;[\/\!]?)([\w\-]+)([^&]*?)(&gt;)/g,
          '$1<span style="color: #569cd6;">$2</span>$3$4'
        );
        
        // Attributes
        formattedLine = formattedLine.replace(
          /(\s+)([\w\-:]+)(=)(['"])/g,
          '$1<span style="color: #9cdcfe;">$2</span>$3$4'
        );
        
        // Replace spaces with non-breaking spaces to preserve indentation
        formattedLine = formattedLine.replace(/^ +/g, match => {
          return '&nbsp;'.repeat(match.length);
        });
        
        return (
          <div 
            key={lineIndex} 
            className="whitespace-pre" 
            dangerouslySetInnerHTML={{ __html: formattedLine || '&nbsp;' }} 
          />
        );
      })}
    </div>
  );
}

function formatCss(code: string): JSX.Element {
  // Split the code by tokens we want to highlight
  const lines = code.split('\n');
  
  return (
    <div>
      {lines.map((line, lineIndex) => {
        // Basic token highlighting for CSS
        let formattedLine = line;
        
        // Selectors
        formattedLine = formattedLine.replace(
          /([.#][\w\-]+)/g,
          '<span style="color: #d7ba7d;">$1</span>'
        );
        
        // Properties
        formattedLine = formattedLine.replace(
          /(\s+)([\w\-]+)(\s*:)/g,
          '$1<span style="color: #9cdcfe;">$2</span>$3'
        );
        
        // Units and values
        formattedLine = formattedLine.replace(
          /:\s*([^;]+)(;|\s*$)/g,
          ': <span style="color: #ce9178;">$1</span>$2'
        );
        
        // Replace spaces with non-breaking spaces to preserve indentation
        formattedLine = formattedLine.replace(/^ +/g, match => {
          return '&nbsp;'.repeat(match.length);
        });
        
        return (
          <div 
            key={lineIndex} 
            className="whitespace-pre" 
            dangerouslySetInnerHTML={{ __html: formattedLine || '&nbsp;' }} 
          />
        );
      })}
    </div>
  );
}

export default CodeViewer;
