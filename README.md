# XAI Grok MCP Automatic Tool Support

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)  
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()  

## Overview

This repository contains **Grok Excess**, a desktop application built with PyQt6 that enhances XAI's Grok (versions 3/4) by providing automatic tool support via integration with MCP (Multi-Computer Protocol) servers. MCP is a protocol used by Anthropic's Claude Desktop for local tool execution (e.g., running scripts, accessing files, or other custom tools on your machine).

The application embeds the Grok web interface (from https://grok.com) in a browser window and automates the following:
- **Agent Mode Initialization**: Sends a custom system prompt to Grok, transforming it into "Grok Excess" – an autonomous AI agent that can think, act, observe, and repeat using tools.
- **Tool Detection and Execution**: Monitors Grok's responses for tool commands in the format `[use_tool: TOOL_NAME(args)]`. When detected, it executes the tool via MCP clients and feeds the output back to Grok as `[Tool Output]: ...`.
- **Tool Management UI**: Injects a native-looking "Agent" button into Grok's web UI, allowing users to enable/disable tools via a modal dialog.
- **MCP Integration**: Automatically loads and connects to MCP servers defined in Claude Desktop's configuration file (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, or equivalent paths on Linux/macOS). Tools from these servers are prefixed as `MCP_<server_name>_<tool_name>`.

This setup enables Grok to act as a self-contained agent for tasks requiring local computation, file access, or external integrations, leveraging Claude's MCP tools without manual intervention.

### Key Features
- **Autonomous Agent Loop**: Grok follows a Think-Act-Observe-Repeat cycle, using tools only when necessary.
- **Platform Awareness**: The system prompt includes OS-specific information (Windows, Linux, or macOS).
- **Secure Execution**: Tools run in isolated MCP sessions with proper lifecycle management (using asyncio and AsyncExitStack).
- **UI Enhancements**: Custom JavaScript injection adds an "Agent" button, tool management modal, and an "Initialize Grok Agent" button for small screens.
- **Error Handling**: Graceful handling of tool parsing errors, disabled tools, and execution failures.

### Limitations
- Requires Claude Desktop installed and configured with MCP servers for any tools to be available.
- No built-in tools; all tools come from MCP configurations.
- WebEngine profile persists data in `./grok_profile` for cookies/session continuity.
- Tested primarily on Windows; Linux/macOS may require adjustments for config paths.
- No internet access in tools (MCP handles local execution only).

## Prerequisites

- **Python 3.8+**: Ensure you have a compatible Python environment.
- **Claude Desktop**: Installed with at least one MCP server configured (e.g., for local tools like shell execution or file I/O). The config file must exist at:
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - Linux/macOS: Equivalent user config directory (e.g., `~/.config/Claude/claude_desktop_config.json` – adjust if needed).
- **Qt WebChannel JavaScript**: The file `qwebchannel.js` is required (not included in this repo due to Qt licensing). Download it from the official Qt sources or copy from your PyQt6 installation (typically in `site-packages/PyQt6/Qt6/qml/QtWebChannel/qwebchannel.js`).
- **Access to Grok**: A valid account on https://grok.com (Grok 3/4 available via free tiers or subscriptions).

## Installation

1. **Clone the Repository**:
   ```
   git clone https://github.com/alxspiker/XAI-Grok-MCP-Automatic-Tool-Support.git
   cd XAI-Grok-MCP-Automatic-Tool-Support
   ```

2. **Install Dependencies**:
   Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   venv\Scripts\activate     # On Windows
   ```
   Then install:
   ```
   pip install -r requirements.txt
   ```

3. **Add Required JavaScript Files**:
   - Place `grok_automator.js` (included in the repo) in the project directory.
   - Download/copy `qwebchannel.js` (from Qt) into the project directory.

4. **Configure MCP Servers** (Optional but Recommended):
   - Open Claude Desktop and set up MCP servers (e.g., a local Python server or shell tool).
   - Ensure the config file includes entries under `"mcpServers"` with keys like `command`, `args`, `env`, and `workingDir`.

## Usage

1. **Run the Application**:
   ```
   python main.py
   ```
   - This launches a window titled "Grok Excess - Agent Mode" with the Grok web interface loaded.
   - The application automatically connects to configured MCP servers and loads tools.

2. **Initialize Agent Mode**:
   - On first load or small screens, click the "Initialize Grok Agent" button (appears at the bottom).
   - This sends the initial system prompt to Grok, including OS info and available tools.
   - Grok will acknowledge the protocol and await tasks.

3. **Manage Tools**:
   - Click the "Agent" button (injected into the top bar of Grok's UI, with a bot icon).
   - A modal appears listing all loaded tools (e.g., `MCP_local_shell_execute`).
   - Enable/disable tools via checkboxes. Changes are saved in memory and applied immediately.

4. **Interact with Grok**:
   - Give Grok a task (e.g., "Write a Python script to list files in the current directory").
   - Grok (as "Grok Excess") will detect if a tool is needed, output a `[use_tool: ...]` command.
   - The app automatically executes the tool via MCP and sends the output back.
   - The loop continues until the task is complete, then Grok provides a final answer.

5. **Example Workflow**:
   - User: "What's the content of my desktop?"
   - Grok: Thinks, outputs `[use_tool: MCP_local_file_read(args='{"path": "~/Desktop"}')]`.
   - App: Executes via MCP, gets output, sends `[Tool Output]: [files listed]`.
   - Grok: Observes, continues or finishes.

6. **Closing the App**:
   - Closes MCP sessions gracefully to avoid resource leaks.

### Debugging Tips
- Check console output for logs (e.g., "Loaded MCP server 'local' with 5 tools.").
- If no tools load, verify Claude config exists and has valid MCP entries.
- JavaScript injection issues: Ensure `qwebchannel.js` and `grok_automator.js` are in the working directory.
- Tool errors appear in Grok as `[Tool Error: ...]`.

## Project Structure

- **`main.py`**: Core Python script handling the PyQt6 app, MCP connections, tool execution, and JS bridging.
- **`grok_automator.js`**: Injected JavaScript for UI modifications (button, modal), message processing, and backend communication.
- **`qwebchannel.js`**: Qt-provided JS for WebChannel communication (must be added manually).
- **`requirements.txt`**: Python dependencies.
- **`README.md`**: This file.
- **`LICENSE`**: MIT License (add if not present).

## Contributing

1. Fork the repo.
2. Create a feature branch: `git checkout -b feature/new-tool-support`.
3. Commit changes: `git commit -m "Add support for custom tools"`.
4. Push: `git push origin feature/new-tool-support`.
5. Open a Pull Request.

We welcome improvements like cross-platform config handling, additional tool parsers, or UI enhancements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for desktop integration.
- Leverages MCP from [Anthropic's Claude Desktop](https://www.anthropic.com/claude) for tool execution.
- Inspired by autonomous AI agent patterns.

For issues, open a GitHub ticket. Last updated: July 10, 2025.