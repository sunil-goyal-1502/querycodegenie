
import React, { useState, useEffect } from 'react';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { AlertCircle, BookOpen, Bot, Code2, FileCode, ChevronLeft, ChevronRight } from 'lucide-react';
import OllamaSelector from '@/components/OllamaSelector';
import SourceInput from '@/components/SourceInput';
import CodeProgress from '@/components/CodeProgress';
import FileExplorer from '@/components/FileExplorer';
import CodeViewer from '@/components/CodeViewer';
import CodeChat from '@/components/CodeChat';
import { CodeIndicesService, IndexingStatus, FileStructure, FileContent } from '@/utils/codeIndicesService';
import { useToast } from '@/components/ui/use-toast';
import { useIsMobile } from '@/hooks/use-mobile';

export default function Index() {
  const [connectionStep, setConnectionStep] = useState<'setup' | 'connected'>('setup');
  const [isOllamaConnected, setIsOllamaConnected] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedTab, setSelectedTab] = useState<'status' | 'files' | 'chat'>('status');
  const [indexingStatus, setIndexingStatus] = useState<IndexingStatus>({
    is_indexing: false,
    progress: 0,
    message: "Waiting to start indexing...",
    stats: {},
    error: null
  });
  const [fileStructure, setFileStructure] = useState<FileStructure>({
    success: false,
    structure: { root: {} }
  });
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [startPolling, setStartPolling] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { toast } = useToast();
  const isMobile = useIsMobile();

  // Poll indexing status
  useEffect(() => {
    if (!startPolling) return;
    
    const pollInterval = setInterval(async () => {
      try {
        const status = await CodeIndicesService.getIndexingStatus();
        setIndexingStatus(status);
        
        // When indexing completes
        if (status.progress === 100 && !status.is_indexing) {
          // Stop polling
          clearInterval(pollInterval);
          
          // Load file structure
          try {
            const structure = await CodeIndicesService.getFileStructure();
            setFileStructure(structure);
          } catch (error) {
            console.error("Error loading file structure:", error);
          }
          
          // Switch to chat tab
          setSelectedTab('chat');
        }
      } catch (error) {
        console.error("Error polling indexing status:", error);
      }
    }, 1000);
    
    return () => clearInterval(pollInterval);
  }, [startPolling]);

  // Handle file selection
  const handleFileSelect = async (filePath: string) => {
    try {
      setSelectedFile(filePath);
      
      const content = await CodeIndicesService.getFileContent(filePath);
      setFileContent(content);
      
      // On mobile, switch to the file view when a file is selected
      if (isMobile) {
        setSelectedTab('files');
      }
    } catch (error) {
      console.error("Error getting file content:", error);
      toast({
        title: "Error",
        description: `Failed to load file: ${error instanceof Error ? error.message : "Unknown error"}`,
        variant: "destructive",
      });
    }
  };

  // Handle Ollama connection
  const handleOllamaConnect = (connected: boolean, models: string[]) => {
    setIsOllamaConnected(connected);
    setAvailableModels(models);
    
    if (connected && models.length > 0) {
      setConnectionStep('connected');
    }
  };

  // Handle source loading
  const handleSourceLoaded = () => {
    setStartPolling(true);
    setSelectedTab('status');
  };

  // Main content based on selected tab
  const renderMainContent = () => {
    switch (selectedTab) {
      case 'status':
        return (
          <div className="h-full flex-1 flex items-center justify-center p-4">
            <div className="w-full max-w-3xl">
              <CodeProgress
                isIndexing={indexingStatus.is_indexing}
                progress={indexingStatus.progress}
                message={indexingStatus.message}
                error={indexingStatus.error}
                stats={indexingStatus.stats}
              />
            </div>
          </div>
        );
      
      case 'files':
        return (
          <div className="h-full flex-1 p-4 overflow-hidden">
            {selectedFile && fileContent ? (
              <CodeViewer
                content={fileContent.content}
                language={fileContent.language}
                filePath={fileContent.file_path}
              />
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <FileCode className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-medium mb-2">No File Selected</h3>
                  <p className="text-sm text-muted-foreground max-w-md">
                    Select a file from the sidebar to view its contents.
                  </p>
                </div>
              </div>
            )}
          </div>
        );
      
      case 'chat':
        return (
          <div className="h-full flex-1 overflow-hidden">
            <CodeChat onFileSelect={handleFileSelect} />
          </div>
        );
      
      default:
        return null;
    }
  };

  // Render setup or main app
  if (connectionStep === 'setup') {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-4">
              <Bot className="h-10 w-10 text-primary" />
              <Code2 className="h-8 w-8 text-primary" />
            </div>
            <h1 className="text-3xl font-bold mb-1">CodeGenie</h1>
            <p className="text-muted-foreground mb-8">Connect to your Ollama server to begin</p>
          </div>
          
          <OllamaSelector onConnect={handleOllamaConnect} />
          
          {isOllamaConnected && (
            <Button 
              className="w-full mt-4" 
              onClick={() => setConnectionStep('connected')}
            >
              Continue
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b py-2 px-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold">CodeGenie</h1>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedTab('status')}
            className={selectedTab === 'status' ? 'bg-secondary' : ''}
          >
            <AlertCircle className="h-4 w-4 mr-1" /> Status
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedTab('files')}
            className={selectedTab === 'files' ? 'bg-secondary' : ''}
          >
            <FileCode className="h-4 w-4 mr-1" /> Files
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedTab('chat')}
            className={selectedTab === 'chat' ? 'bg-secondary' : ''}
          >
            <Bot className="h-4 w-4 mr-1" /> Chat
          </Button>
        </div>
      </header>
      
      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        {startPolling ? (
          <ResizablePanelGroup direction="horizontal" className="h-full">
            {/* Sidebar */}
            <ResizablePanel
              defaultSize={20}
              minSize={15}
              maxSize={30}
              collapsible={true}
              collapsedSize={0}
              onCollapse={() => setSidebarCollapsed(true)}
              onExpand={() => setSidebarCollapsed(false)}
              className={sidebarCollapsed ? 'hidden' : 'border-r'}
            >
              <div className="h-full flex flex-col">
                <div className="p-2 border-b">
                  <h2 className="text-sm font-medium">Project Explorer</h2>
                </div>
                <ScrollArea className="flex-1">
                  {fileStructure.success ? (
                    <FileExplorer
                      structure={fileStructure.structure.root}
                      onFileSelect={handleFileSelect}
                      selectedFile={selectedFile || undefined}
                    />
                  ) : (
                    <div className="p-4 text-center text-muted-foreground">
                      <p className="text-sm">No files loaded yet</p>
                    </div>
                  )}
                </ScrollArea>
              </div>
            </ResizablePanel>
            
            <ResizableHandle withHandle />
            
            {/* Main panel */}
            <ResizablePanel defaultSize={80} minSize={30}>
              <div className="h-full flex flex-col">
                {sidebarCollapsed && (
                  <div className="absolute top-1/2 left-0 z-10">
                    <Button
                      variant="secondary"
                      size="icon"
                      className="h-8 w-8 rounded-full shadow-md"
                      onClick={() => setSidebarCollapsed(false)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}
                {renderMainContent()}
              </div>
            </ResizablePanel>
          </ResizablePanelGroup>
        ) : (
          <div className="h-full flex items-center justify-center p-4">
            <div className="w-full max-w-md">
              <SourceInput onSourceLoaded={handleSourceLoaded} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
