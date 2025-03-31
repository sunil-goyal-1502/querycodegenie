
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Union, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-coder"):
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api"
        logger.info(f"Initialized OllamaClient with model: {model} at {base_url}")
    
    def test_connection(self) -> Dict[str, Union[bool, str]]:
        """Test the connection to the Ollama server."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                available_models = response.json().get("models", [])
                model_names = [model["name"] for model in available_models]
                
                if self.model in model_names:
                    return {
                        "connected": True,
                        "message": f"Successfully connected to Ollama server. Model '{self.model}' is available.",
                        "available_models": model_names
                    }
                else:
                    suggested_model = next((model for model in model_names if "deepseek" in model or "coder" in model), model_names[0] if model_names else None)
                    return {
                        "connected": True,
                        "message": f"Connected to Ollama server, but model '{self.model}' is not available. Available models: {', '.join(model_names)}",
                        "suggested_model": suggested_model,
                        "available_models": model_names
                    }
            else:
                return {
                    "connected": False,
                    "message": f"Server responded with status code {response.status_code}",
                    "error": response.text
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama server: {str(e)}")
            return {
                "connected": False,
                "message": f"Failed to connect to Ollama server at {self.base_url}. Is the server running?",
                "error": str(e)
            }
    
    def set_model(self, model_name: str) -> None:
        """Change the model being used."""
        self.model = model_name
        logger.info(f"Model changed to: {model_name}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, 
               max_tokens: int = 2048, stream: bool = False) -> Dict[str, Any]:
        """Generate a completion using the Ollama API."""
        url = f"{self.api_url}/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            logger.info(f"Sending request to Ollama with model {self.model}")
            
            if stream:
                # Handle streaming response
                response_text = ""
                with requests.post(url, json=payload, stream=True) as response:
                    if response.status_code != 200:
                        logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status_code} - {response.text}"
                        }
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "response" in chunk:
                                    response_text += chunk["response"]
                                    yield chunk["response"]
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to decode JSON from line: {line}")
                
                return {
                    "success": True,
                    "response": response_text,
                    "model": self.model
                }
            else:
                # Handle regular response
                response = requests.post(url, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "response": result.get("response", ""),
                        "model": self.model,
                        "total_duration": result.get("total_duration"),
                        "load_duration": result.get("load_duration"),
                        "prompt_eval_count": result.get("prompt_eval_count"),
                        "eval_count": result.get("eval_count"),
                        "eval_duration": result.get("eval_duration")
                    }
                else:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code} - {response.text}"
                    }
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Ollama failed: {str(e)}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

    def analyze_codebase(self, codebase_summary: Dict, files_content: Dict[str, str], 
                       dependencies: Dict[str, List[str]]) -> Dict[str, Any]:
        """Analyze the codebase structure and provide high-level insights."""
        system_prompt = """You are CodeGenie, an expert code analyzer. Your task is to analyze a codebase and provide insights about its structure, architecture, and dependencies. Focus on:
1. The overall architecture and design patterns
2. Main components and their responsibilities
3. How files and modules are related to each other
4. Key functionality of the codebase
Be specific, technical, and accurate in your analysis."""
        
        prompt = f"""I need you to analyze this codebase:

## Codebase Summary
{json.dumps(codebase_summary, indent=2)}

## Files and Their Dependencies
The codebase contains {len(files_content)} files. Here are the key dependencies:
{json.dumps(dependencies, indent=2)}

Based on this information, please:
1. Describe the overall architecture and structure of this codebase
2. Identify the main components and their responsibilities 
3. Explain how the components are related to each other
4. Identify key functionality of the application
5. List any design patterns or architectural approaches you observe

Please be specific and technical in your analysis.
"""
        
        return self.generate(prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=4096)
    
    def query_code(self, query: str, relevant_files: Dict[str, str], 
                 dependencies: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Answer a query about specific code files."""
        system_prompt = """You are CodeGenie, an expert code assistant. Your task is to answer queries about code with high precision and technical accuracy. When examining code:
1. Provide specific explanations referring to actual code snippets
2. If asked how something works, trace through the code execution step-by-step
3. When explaining relationships between files, be explicit about how they interact
4. For questions about implementing new features, provide specific, implementable code suggestions
5. Always ground your answers in the actual code you've been provided

Be technical, precise, and helpful."""
        
        # Create a context that includes the content of all relevant files
        context = "Here are the relevant code files for your query:\n\n"
        
        for file_path, content in relevant_files.items():
            context += f"## File: {file_path}\n```\n{content}\n```\n\n"
        
        if dependencies:
            context += "## Dependencies between these files:\n"
            context += json.dumps(dependencies, indent=2) + "\n\n"
        
        prompt = f"{context}\n\nQuery: {query}\n\nPlease answer the query based on these code files."
        
        return self.generate(prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=4096)
    
    def suggest_code_changes(self, query: str, relevant_files: Dict[str, str], 
                          dependencies: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """Suggest changes to implement new features or fix issues."""
        system_prompt = """You are CodeGenie, an expert programmer. Your task is to suggest specific code changes to implement features or fix issues. When suggesting changes:
1. Provide complete, working code snippets that can be directly implemented
2. Clearly indicate which files need to be modified and exactly where in each file
3. Explain the reasoning behind your suggested changes
4. Consider edge cases and error handling
5. Ensure your suggested changes maintain coding style consistency with the existing codebase

Be detailed, precise, and ensure your suggestions are ready to implement."""
        
        # Create a context that includes the content of all relevant files
        context = "Here are the relevant code files for implementing the requested changes:\n\n"
        
        for file_path, content in relevant_files.items():
            context += f"## File: {file_path}\n```\n{content}\n```\n\n"
        
        if dependencies:
            context += "## Dependencies between these files:\n"
            context += json.dumps(dependencies, indent=2) + "\n\n"
        
        prompt = f"{context}\n\nFeature Request: {query}\n\nPlease suggest specific code changes to implement this feature or fix this issue. For each change, specify the file path, the location of the change, and provide the complete code snippet to be added or modified."
        
        return self.generate(prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=8192)
    
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
        
        return self.generate(prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=2048)
