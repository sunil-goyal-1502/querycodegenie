import os
import json
import logging
import requests
from typing import Dict, List, Optional, Union, Any, Generator
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, model: str = "llama3:8b"):
        self.model = model
        self.base_url = "http://localhost:11434"
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized OllamaClient with model: {model}")
    
    def test_connection(self) -> bool:
        """Test connection to Ollama server."""
        try:
            # First try to connect to the server
            self.logger.info(f"Testing connection to Ollama server at {self.base_url}")
            self.logger.info(f"Attempting to get available models from {self.base_url}/api/tags")
            
            response = requests.get(f"{self.base_url}/api/tags")
            self.logger.info(f"Ollama server response status: {response.status_code}")
            self.logger.info(f"Ollama server response headers: {response.headers}")
            
            if response.status_code != 200:
                self.logger.error(f"Ollama server returned non-200 status code: {response.status_code}")
                self.logger.error(f"Response content: {response.text}")
                return False
                
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            self.logger.info(f"Ollama server response data: {data}")
            
            if not isinstance(data, dict):
                self.logger.error("Invalid response format from Ollama server")
                return False
                
            # Check if models are available
            models = data.get("models", [])
            if not models:
                self.logger.warning("No models available on Ollama server")
                return False
                
            # Check if our model is available
            model_names = [model.get("name") for model in models if isinstance(model, dict)]
            self.logger.info(f"Available models: {model_names}")
            
            if not model_names:
                self.logger.error("Invalid model format in Ollama response")
                return False
                
            if self.model in model_names:
                self.logger.info(f"Successfully connected to Ollama server. Model '{self.model}' is available.")
                return True
            else:
                # Try to find a similar model
                similar_models = [name for name in model_names if "llama" in name.lower()]
                if similar_models:
                    self.logger.warning(f"Model '{self.model}' not found. Similar models available: {', '.join(similar_models)}")
                    # Use the first similar model
                    self.model = similar_models[0]
                    self.logger.info(f"Using similar model: {self.model}")
                    return True
                else:
                    self.logger.warning(f"Connected to Ollama server, but model '{self.model}' is not available. Available models: {', '.join(model_names)}")
                    return False
                
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Failed to connect to Ollama server. Is it running? Error: {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error testing Ollama connection: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing Ollama response: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error testing Ollama connection: {str(e)}")
            return False
    
    def generate(self, prompt: str, temperature: float = 0.7, stream: bool = True) -> Union[str, Generator[str, None, None]]:
        """Generate text using the Ollama API."""
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "stream": stream
            }
            
            response = requests.post(url, json=data, stream=stream)
            self.logger.info(f"The response from LLM is:")
            self.logger.info(response)
            
            if stream:
                def generate_stream():
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                if 'response' in chunk:
                                    yield chunk['response']
                            except json.JSONDecodeError:
                                continue
                return generate_stream()
            else:
                result = response.json()
                return result.get('response', '')
                
        except Exception as e:
            self.logger.error(f"Error generating text: {str(e)}")
            return ""
    
    def analyze_codebase(self, codebase: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the entire codebase."""
        try:
            prompt = f"""Please analyze this codebase and provide a comprehensive overview:

Codebase Summary:
{json.dumps(codebase['summary'], indent=2)}

Files:
{json.dumps([{'path': f['path'], 'language': f['language']} for f in codebase['files']], indent=2)}

Dependencies:
{json.dumps(codebase['dependencies'], indent=2)}

Please provide:
1. Overall architecture and structure
2. Key components and their relationships
3. Main functionality and purpose
4. Notable patterns or design decisions
5. Potential areas for improvement

Format your response in a clear, structured way."""

            response = self.generate(prompt, temperature=0.3)
            if isinstance(response, Generator):
                response = ''.join(response)
            
            return {
                "analysis": response,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing codebase: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }
    
    def query_code(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query the codebase with a specific question."""
        try:
            prompt = f"""Please answer this question about the codebase:

Question: {query}

Context:
{json.dumps(context, indent=2)}

Please provide:
1. A direct answer to the question
2. Relevant code snippets or examples
3. Additional context or related information
4. Any caveats or limitations

Format your response in a clear, structured way."""

            response = self.generate(prompt, temperature=0.3)
            if isinstance(response, Generator):
                response = ''.join(response)
            
            return {
                "answer": response,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Error querying code: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }
    
    def suggest_code_changes(self, code: str, suggestion: str) -> Dict[str, Any]:
        """Suggest code changes based on a description."""
        try:
            prompt = f"""Please suggest code changes based on this description:

Code:
{code}

Suggestion:
{suggestion}

Please provide:
1. The modified code with changes
2. Explanation of the changes
3. Any additional considerations
4. Potential impact of the changes

Format your response in a clear, structured way."""

            response = self.generate(prompt, temperature=0.3)
            if isinstance(response, Generator):
                response = ''.join(response)
            
            return {
                "suggestion": response,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Error suggesting code changes: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }

    def set_model(self, model_name: str) -> None:
        """Change the model being used."""
        self.model = model_name
        self.logger.info(f"Model changed to: {model_name}")
    
    def find_relevant_files(self, query: str, file_list: List[str], file_summaries: Dict[str, str]) -> Dict[str, Any]:
        """Identify which files are most relevant to a specific query."""
        system_prompt = """You are CodeGenie, an expert code assistant. Your task is to identify which files in a codebase are most relevant to a specific query or feature request. When analyzing relevance:
1. Consider both direct relevance (files that would need to be modified) and contextual relevance (files that provide necessary context)
2. Rank files by relevance, with the most relevant first
3. Provide a brief explanation of why each file is relevant
4. Be comprehensive - don't miss files that might be affected
5. Consider dependencies and potential ripple effects of changes

Be precise and thorough in your analysis."""
        
        # Create a context with summaries of all files
        context = f"Query: {query}\n\nHere are summaries of files in the codebase:\n\n"
        
        for file_path, summary in file_summaries.items():
            context += f"## {file_path}\n{summary}\n\n"
        
        prompt = f"{context}\n\nPlease identify and rank the files most relevant to this query. For each file, explain why it's relevant and how it relates to the query."
        
        return self.generate(prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=16384)

    def get_available_models(self) -> List[str]:
        """Get list of available models from Ollama server."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            if not isinstance(data, dict):
                self.logger.error("Invalid response format from Ollama server")
                return []
                
            models = data.get("models", [])
            if not models:
                self.logger.warning("No models available on Ollama server")
                return []
                
            model_names = [model.get("name") for model in models if isinstance(model, dict)]
            if not model_names:
                self.logger.error("Invalid model format in Ollama response")
                return []
                
            self.logger.info(f"Available models: {', '.join(model_names)}")
            return model_names
                
        except requests.exceptions.ConnectionError:
            self.logger.error("Failed to connect to Ollama server. Is it running?")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting available models: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing Ollama response: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error getting available models: {str(e)}")
            return []
