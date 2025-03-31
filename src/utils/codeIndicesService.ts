import { toast } from "@/components/ui/use-toast";

// Base URL for API - change to the actual Python backend URL
const API_BASE_URL = "http://localhost:5000/api";

// Types for the service
export type IndexingStatus = {
  is_indexing: boolean;
  progress: number;
  message: string;
  stats: {
    total_files?: number;
    indexed_files?: number;
    skipped_files?: number;
    binary_files?: number;
    by_language?: Record<string, number>;
  };
  error: string | null;
};

export type FileContent = {
  success: boolean;
  file_path: string;
  content: string;
  language: string;
  error?: string;
};

export type FileStructure = {
  success: boolean;
  structure: {
    root: Record<string, any>;
  };
  error?: string;
};

export type LLMResponse = {
  success: boolean;
  response: string;
  model?: string;
  relevant_files?: string[];
  error?: string;
};

export type OllamaStatus = {
  connected: boolean;
  message: string;
  suggested_model?: string;
  available_models?: string[];
  error?: string;
};

// Service class for code indexing and analysis
export class CodeIndicesService {
  // Test connection to Ollama server
  static async testOllamaConnection(
    baseUrl: string = "http://localhost:11434",
    model: string = "deepseek-coder"
  ): Promise<OllamaStatus> {
    try {
      console.log(`Testing connection to Ollama at ${baseUrl} with model ${model}`);
      console.log(`Backend URL: ${API_BASE_URL}/test-ollama`);
      
      const response = await fetch(`${API_BASE_URL}/test-ollama`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ base_url: baseUrl, model }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`HTTP error ${response.status}: ${errorText}`);
        throw new Error(`HTTP error ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      console.log("Ollama connection test result:", result);
      return result;
    } catch (error) {
      console.error("Error testing Ollama connection:", error);
      return {
        connected: false,
        message: `Failed to connect to the backend: ${error instanceof Error ? error.message : String(error)}. Make sure your backend server is running at ${API_BASE_URL} and accessible from your browser.`,
      };
    }
  }

  // Set the LLM model to use
  static async setModel(model: string): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/set-model`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ model }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error setting model:", error);
      return {
        success: false,
        message: `Failed to set model: ${error instanceof Error ? error.message : String(error)}`,
      };
    }
  }

  // Load a Git repository for indexing
  static async loadRepository(
    repoUrl: string,
    authToken?: string
  ): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/load-repo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          auth_token: authToken,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error loading repository:", error);
      return {
        success: false,
        message: `Failed to load repository: ${error instanceof Error ? error.message : String(error)}`,
      };
    }
  }

  // Load a local directory for indexing
  static async loadDirectory(
    directoryPath: string
  ): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/load-directory`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          directory_path: directoryPath,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error loading directory:", error);
      return {
        success: false,
        message: `Failed to load directory: ${error instanceof Error ? error.message : String(error)}`,
      };
    }
  }

  // Get the current indexing status
  static async getIndexingStatus(): Promise<IndexingStatus> {
    try {
      const response = await fetch(`${API_BASE_URL}/indexing-status`);

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error getting indexing status:", error);
      return {
        is_indexing: false,
        progress: 0,
        message: `Failed to get indexing status: ${error instanceof Error ? error.message : String(error)}`,
        stats: {},
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Get the file structure of the indexed codebase
  static async getFileStructure(): Promise<FileStructure> {
    try {
      const response = await fetch(`${API_BASE_URL}/file-structure`);

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error getting file structure:", error);
      return {
        success: false,
        structure: { root: {} },
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Get the content of a specific file
  static async getFileContent(filePath: string): Promise<FileContent> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/file-content?path=${encodeURIComponent(filePath)}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error getting file content:", error);
      return {
        success: false,
        file_path: filePath,
        content: "",
        language: "unknown",
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Search for a term in the codebase
  static async searchCodebase(searchTerm: string): Promise<{
    success: boolean;
    results: Record<string, any[]>;
    error?: string;
  }> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/search?term=${encodeURIComponent(searchTerm)}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error searching codebase:", error);
      return {
        success: false,
        results: {},
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Get the codebase summary
  static async getCodebaseSummary(): Promise<{
    success: boolean;
    summary: Record<string, any>;
    error?: string;
  }> {
    try {
      const response = await fetch(`${API_BASE_URL}/codebase-summary`);

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error getting codebase summary:", error);
      return {
        success: false,
        summary: {},
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Analyze the codebase structure
  static async analyzeCodebase(): Promise<LLMResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/analyze-codebase`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error analyzing codebase:", error);
      return {
        success: false,
        response: "",
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Query the codebase
  static async queryCode(query: string, stream: boolean = false): Promise<LLMResponse | ReadableStream> {
    try {
      if (stream) {
        const response = await fetch(`${API_BASE_URL}/query`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query, stream }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        return response.body as ReadableStream;
      } else {
        const response = await fetch(`${API_BASE_URL}/query`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        return await response.json();
      }
    } catch (error) {
      console.error("Error querying code:", error);
      return {
        success: false,
        response: "",
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Suggest code changes
  static async suggestCodeChanges(query: string, stream: boolean = false): Promise<LLMResponse | ReadableStream> {
    try {
      if (stream) {
        const response = await fetch(`${API_BASE_URL}/suggest-changes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query, stream }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        return response.body as ReadableStream;
      } else {
        const response = await fetch(`${API_BASE_URL}/suggest-changes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        return await response.json();
      }
    } catch (error) {
      console.error("Error suggesting code changes:", error);
      return {
        success: false,
        response: "",
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  // Get related files
  static async getRelatedFiles(filePath: string): Promise<{
    success: boolean;
    related: Record<string, any>;
    error?: string;
  }> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/related-files?path=${encodeURIComponent(filePath)}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Error getting related files:", error);
      return {
        success: false,
        related: {},
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }
}

// Helper methods for handling API responses
export const handleApiError = (
  error: unknown,
  defaultMessage: string = "An error occurred"
): string => {
  console.error(error);
  
  if (typeof error === "string") {
    toast({
      title: "Error",
      description: error,
      variant: "destructive",
    });
    return error;
  } else if (error instanceof Error) {
    toast({
      title: "Error",
      description: error.message,
      variant: "destructive",
    });
    return error.message;
  } else {
    toast({
      title: "Error",
      description: defaultMessage,
      variant: "destructive",
    });
    return defaultMessage;
  }
};
