
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { GitBranch, Folder, KeyRound, Loader2 } from 'lucide-react';
import { CodeIndicesService } from '@/utils/codeIndicesService';
import { useToast } from '@/components/ui/use-toast';

type SourceInputProps = {
  onSourceLoaded: () => void;
  className?: string;
};

export function SourceInput({ onSourceLoaded, className }: SourceInputProps) {
  const [activeTab, setActiveTab] = useState('repo');
  const [repoUrl, setRepoUrl] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [directoryPath, setDirectoryPath] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const handleLoadRepo = async () => {
    if (!repoUrl) {
      toast({
        title: "Missing Input",
        description: "Please enter a repository URL",
        variant: "destructive",
      });
      return;
    }
    
    setIsLoading(true);
    try {
      const result = await CodeIndicesService.loadRepository(repoUrl, authToken || undefined);
      
      if (result.success) {
        toast({
          description: result.message,
        });
        onSourceLoaded();
      } else {
        toast({
          title: "Loading Failed",
          description: result.message,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error("Error loading repository:", error);
      toast({
        title: "Loading Error",
        description: error instanceof Error ? error.message : "Failed to load repository",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadDirectory = async () => {
    if (!directoryPath) {
      toast({
        title: "Missing Input",
        description: "Please enter a directory path",
        variant: "destructive",
      });
      return;
    }
    
    setIsLoading(true);
    try {
      const result = await CodeIndicesService.loadDirectory(directoryPath);
      
      if (result.success) {
        toast({
          description: result.message,
        });
        onSourceLoaded();
      } else {
        toast({
          title: "Loading Failed",
          description: result.message,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error("Error loading directory:", error);
      toast({
        title: "Loading Error",
        description: error instanceof Error ? error.message : "Failed to load directory",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={className}>
      <h2 className="text-xl font-semibold mb-4">Load Your Code</h2>
      
      <Tabs 
        defaultValue="repo" 
        value={activeTab} 
        onValueChange={setActiveTab}
        className="w-full"
      >
        <TabsList className="grid grid-cols-2 mb-4">
          <TabsTrigger value="repo" className="flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Git Repository
          </TabsTrigger>
          <TabsTrigger value="directory" className="flex items-center gap-2">
            <Folder className="h-4 w-4" />
            Local Directory
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="repo" className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="repo-url">Repository URL</Label>
            <Input
              id="repo-url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/username/repository"
            />
            <p className="text-xs text-muted-foreground">
              Enter the URL of a public Git repository
            </p>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="auth-token">
              Authentication Token <span className="text-muted-foreground">(Optional)</span>
            </Label>
            <div className="relative">
              <KeyRound className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                id="auth-token"
                type="password"
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                placeholder="For private repositories"
                className="pl-9"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              For private repositories, provide a personal access token
            </p>
          </div>
          
          <Button 
            onClick={handleLoadRepo}
            disabled={isLoading || !repoUrl}
            className="w-full"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </>
            ) : (
              <>Load Repository</>
            )}
          </Button>
        </TabsContent>
        
        <TabsContent value="directory" className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="directory-path">Directory Path</Label>
            <Input
              id="directory-path"
              value={directoryPath}
              onChange={(e) => setDirectoryPath(e.target.value)}
              placeholder="/path/to/your/code"
            />
            <p className="text-xs text-muted-foreground">
              Enter the absolute path to a local directory containing your code
            </p>
          </div>
          
          <Button 
            onClick={handleLoadDirectory}
            disabled={isLoading || !directoryPath}
            className="w-full"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </>
            ) : (
              <>Load Directory</>
            )}
          </Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default SourceInput;
