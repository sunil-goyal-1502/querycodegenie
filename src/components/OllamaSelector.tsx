
import { useState } from 'react';
import { Check, ChevronsUpDown, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { CodeIndicesService } from '@/utils/codeIndicesService';
import { useToast } from '@/components/ui/use-toast';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertCircle } from 'lucide-react';

type OllamaSelectorProps = {
  onConnect: (connected: boolean, models: string[]) => void;
  className?: string;
};

export function OllamaSelector({ onConnect, className }: OllamaSelectorProps) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('deepseek-coder');
  const [serverUrl, setServerUrl] = useState('http://localhost:11434');
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const { toast } = useToast();

  const handleConnect = async () => {
    setIsConnecting(true);
    setConnectionError(null);
    try {
      console.log("Attempting to connect to Ollama server at:", serverUrl);
      const result = await CodeIndicesService.testOllamaConnection(serverUrl, selectedModel);
      
      if (result.connected) {
        setIsConnected(true);
        
        if (result.available_models) {
          setModels(result.available_models);
          
          if (result.suggested_model && !result.available_models.includes(selectedModel)) {
            setSelectedModel(result.suggested_model);
            await CodeIndicesService.setModel(result.suggested_model);
            toast({
              description: `Model changed to ${result.suggested_model} because the requested model wasn't available.`,
            });
          }
        }
        
        toast({
          description: result.message,
        });
        
        onConnect(true, result.available_models || []);
      } else {
        setIsConnected(false);
        setConnectionError(result.message);
        toast({
          title: "Connection Failed",
          description: result.message,
          variant: "destructive",
        });
        onConnect(false, []);
      }
    } catch (error) {
      console.error("Error connecting to Ollama:", error);
      const errorMessage = error instanceof Error ? error.message : "Failed to connect to Ollama server";
      setConnectionError(errorMessage);
      toast({
        title: "Connection Error",
        description: errorMessage,
        variant: "destructive",
      });
      onConnect(false, []);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleModelChange = async (model: string) => {
    setSelectedModel(model);
    setOpen(false);
    
    if (isConnected) {
      try {
        const result = await CodeIndicesService.setModel(model);
        if (result.success) {
          toast({
            description: `Model changed to ${model}`,
          });
        } else {
          toast({
            title: "Model Change Failed",
            description: result.message,
            variant: "destructive",
          });
        }
      } catch (error) {
        console.error("Error changing model:", error);
        toast({
          title: "Model Change Error",
          description: error instanceof Error ? error.message : "Failed to change model",
          variant: "destructive",
        });
      }
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      <div className="space-y-2">
        <Label htmlFor="server-url">Ollama Server URL</Label>
        <div className="flex space-x-2">
          <Input
            id="server-url"
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            placeholder="http://localhost:11434"
            className="flex-1"
          />
          <Button 
            onClick={handleConnect}
            disabled={isConnecting}
            className="min-w-24"
          >
            {isConnecting ? (
              <span className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-primary-foreground animate-pulse"></span>
                Connecting
              </span>
            ) : isConnected ? (
              <span className="flex items-center gap-2">
                <Check className="h-4 w-4" />
                Connected
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Server className="h-4 w-4" />
                Connect
              </span>
            )}
          </Button>
        </div>
      </div>

      {connectionError && (
        <Alert variant="destructive" className="mt-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Connection Error</AlertTitle>
          <AlertDescription>
            {connectionError}
            <div className="mt-2 text-xs">
              Make sure:
              <ul className="list-disc pl-5 mt-1">
                <li>Your Ollama server is running</li>
                <li>The URL is correct (including protocol)</li>
                <li>The backend server is running at http://localhost:5000</li>
                <li>You're accessing this app from the same machine where Ollama is running</li>
              </ul>
            </div>
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label>Model</Label>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={open}
              disabled={!isConnected || models.length === 0}
              className="w-full justify-between"
            >
              {selectedModel}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[200px] p-0">
            <Command>
              <CommandInput placeholder="Search models..." className="h-9" />
              <CommandEmpty>No models found.</CommandEmpty>
              <CommandGroup>
                {models.map((model) => (
                  <CommandItem
                    key={model}
                    value={model}
                    onSelect={() => handleModelChange(model)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        selectedModel === model ? "opacity-100" : "opacity-0"
                      )}
                    />
                    {model}
                  </CommandItem>
                ))}
              </CommandGroup>
            </Command>
          </PopoverContent>
        </Popover>
        {!isConnected && (
          <p className="text-xs text-muted-foreground">
            Connect to an Ollama server to select a model
          </p>
        )}
      </div>
    </div>
  );
}

export default OllamaSelector;
