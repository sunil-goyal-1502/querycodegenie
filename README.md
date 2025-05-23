
# CodeGenie - Intelligent Code Explorer

CodeGenie is a tool for indexing, analyzing, and querying codebases in any programming language using natural language. It connects to a local Ollama server running open-source language models to provide intelligent responses about your code.

## Features

- Index code from Git repositories or local directories
- Analyze code structure and dependencies
- Ask questions about your codebase in natural language
- Get suggestions for implementing new features
- View and navigate through your codebase
- Support for any programming language

## Setup Instructions

### Prerequisites

1. **Ollama Server**: You need to have Ollama running locally with a code-focused model.
   - Download and install [Ollama](https://ollama.ai/download)
   - Pull a code-focused model like DeepSeek Coder:
     ```
     ollama pull deepseek-coder
     ```
   - Start the Ollama server (usually runs on http://localhost:11434)

2. **Python**: For the backend code indexing service
   - Python 3.7 or higher
   - Install required packages:
     ```
     pip install -r backend_requirements.txt
     ```

### Running the Application

1. **Start the backend server**:
   ```
   python run_backend.py
   ```
   This will start the Flask server on http://localhost:5000

2. **Important: Both frontend and backend must run on the same machine**
   - The frontend web application needs to access:
     - The backend server at http://localhost:5000
     - The Ollama server (typically at http://localhost:11434)
   - If accessing via a remote browser, use port forwarding or a VPN

3. **Start the frontend**:
   ```
   npm run dev
   ```
   This will start the React application

4. **Connect to Ollama**:
   - Open the app in your browser
   - Enter your Ollama server URL (default: http://localhost:11434)
   - Select the model you want to use (e.g., deepseek-coder)
   - Click "Connect"

5. **Troubleshooting Connection Issues**:
   - Make sure the backend server is running and accessible
   - Check that Ollama is running on the specified URL
   - Verify no firewalls are blocking the connections
   - If using Docker or similar, ensure proper network configuration

6. **Load your code**:
   - Choose between loading from a Git repository or a local directory
   - For repositories, paste the Git URL (and authentication token if needed)
   - For local directories, enter the absolute path

7. **Wait for indexing to complete**:
   - The app will display the indexing progress
   - Once complete, you can browse files or start querying your code

8. **Interact with your code**:
   - Ask questions about your codebase
   - Navigate through files and explore dependencies
   - Get suggestions for implementing new features

## Technologies Used

- **Frontend**: React, TypeScript, TailwindCSS, shadcn/ui
- **Backend**: Flask, Python
- **LLM**: Ollama with DeepSeek-Coder or other code models

## License

MIT
