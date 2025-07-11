import sys
import os
import json
import re
import platform
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from collections.abc import AsyncIterator
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, QDir, pyqtSlot, QObject
from PyQt6.QtWebChannel import QWebChannel
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters, types

class JsApi(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    @pyqtSlot(str)
    def tool_triggered(self, tool_command):
        print(f"Tool triggered from JS: {tool_command}")
        output = "Error: Tool execution failed."
        tool_name = "Unknown"
        try:
            match = re.search(r"\[use_tool:\s*(\w+)\((.*)\)\]", tool_command, re.DOTALL)
            if not match:
                output = "Error: Could not parse tool command with Regex."
                self.main_window.send_tool_output_to_grok(output)
                return

            tool_name = match.group(1)
            args_str = match.group(2)

            if tool_name.startswith("MCP_"):
                if not self.main_window.tools.get(tool_name, {}).get("enabled"):
                    output = "Error: Tool is not enabled."
                else:
                    # Parse MCP tool: MCP_<server>_<tool>(args_json)
                    parts = tool_name.split("_", 2)
                    if len(parts) != 3:
                        output = "Error: Invalid MCP tool format."
                    else:
                        _, server_name, mcp_tool_name = parts
                        args_match = re.search(r"args='(.*)'", args_str, re.DOTALL)
                        tool_args = json.loads(args_match.group(1)) if args_match else {}

                        if server_name in self.main_window.mcp_clients:
                            client_session = self.main_window.mcp_clients[server_name]
                            loop = asyncio.get_event_loop()
                            result = loop.run_until_complete(client_session.call_tool(mcp_tool_name, tool_args))
                            output = json.dumps(result) if isinstance(result, dict) else str(result)
                        else:
                            output = "Error: MCP server not found."
            else:
                output = f"Error: Tool '{tool_name}' is not recognized."

        except Exception as e:
            output = f"[Tool Error: {tool_name}]: {str(e)}"

        print(f"Tool output:\n{output}")
        self.main_window.send_tool_output_to_grok(output)

    @pyqtSlot(result=str)
    def get_tools(self):
        return json.dumps(self.main_window.tools)

    @pyqtSlot(str, bool)
    def set_tool_enabled(self, tool_name, enabled):
        if tool_name in self.main_window.tools:
            self.main_window.tools[tool_name]["enabled"] = enabled
            print(f"Set tool '{tool_name}' enabled state to: {enabled}")

    @pyqtSlot()
    def send_initial_system_prompt(self):
        os_name = platform.system()
        os_info = "Unknown"
        
        if os_name == "Windows":
            os_info = f"You are operating on a **Windows** system."
        elif os_name == "Linux":
            os_info = f"You are operating on a **Linux** system."
        elif os_name == "Darwin":
            os_info = f"You are operating on a **macOS** system."

        tool_instructions = []
        for name, details in self.main_window.tools.items():
            if details.get("enabled"):
                tool_instructions.append(f"### {name}\n- **Description**: {details['description']}\n- **Syntax**: `{details['syntax']}`")
        
        full_prompt = (
            "**[AGENT PROTOCOL INITIATED]**\n\n"
            "1.  **Persona**: You are Grok Excess, a helpful and autonomous AI agent. Your goal is to use the tools at your disposal to achieve the user's objective.\n\n"
            "2.  **Environment**: " + os_info + "\n\n"
            "3.  **Core Directive**: When a user gives you a task, you must **autonomously** perform the following loop:\n"
            "    a.  **Think**: Analyze the user's request and the information you have. Formulate a plan or a single next step.\n"
            "    b.  **Act**: If a tool can help you execute your step, you **MUST** respond with **nothing but** the tool command. Do not add conversational text or explanations.\n"
            "    c.  **Observe**: I will provide the result of your action in a `[Tool Output]: ...` block. Analyze this output to inform your next thought.\n"
            "    d.  **Repeat**: Continue this cycle until the user's task is fully completed or you determine it cannot be completed. If you are finished, provide the final answer to the user in a clear, natural way.\n\n"
            "4.  **Available Tools**:\n" + "\n".join(tool_instructions) + "\n\n"
            "Acknowledge this protocol and await your first task."
        )
        
        self.main_window.send_text_to_grok(full_prompt)

class GrokExcess(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Excess - Agent Mode")
        self.setGeometry(100, 100, 1200, 800)
        self.tools = {}
        self.mcp_clients = {}  # server_name: ClientSession
        self.mcp_processes = {}  # server_name: Popen
        self.lifespan_stack = AsyncExitStack()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.setup_mcp_servers())
        profile_dir = os.path.abspath("grok_profile")
        if not os.path.exists(profile_dir): os.makedirs(profile_dir)
        self.profile = QWebEngineProfile("GrokStorage", self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setPersistentStoragePath(QDir.toNativeSeparators(profile_dir))
        self.page = QWebEnginePage(self.profile, self)
        self.channel = QWebChannel()
        self.js_api = JsApi(self)
        self.channel.registerObject("backend", self.js_api)
        self.page.setWebChannel(self.channel)
        self.browser = QWebEngineView()
        self.browser.setPage(self.page)
        self.browser.load(QUrl("https://grok.com"))
        self.setCentralWidget(self.browser)
        self.browser.loadFinished.connect(self.on_load_finished)

    async def setup_mcp_servers(self):
        config_path = os.path.expandvars(r"%APPDATA%\Claude\claude_desktop_config.json")
        if not os.path.exists(config_path):
            print("Warning: Claude config not found. No MCP servers loaded.")
            return

        with open(config_path, "r") as f:
            config = json.load(f)
        
        mcp_servers = config.get("mcpServers", {})
        for server_name, server_config in mcp_servers.items():
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", {})
            cwd = server_config.get("workingDir")
            if command:
                params = StdioServerParameters(command=command, args=args, env=env, cwd=cwd)
                read, write = await self.lifespan_stack.enter_async_context(stdio_client(params))
                session = await self.lifespan_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                tools_response = await session.list_tools()
                self.mcp_clients[server_name] = session
                for tool in tools_response.tools:
                    prefixed_name = f"MCP_{server_name}_{tool.name}"
                    syntax = f"[use_tool: {prefixed_name}(args='<JSON dict of args>')]"
                    self.tools[prefixed_name] = {
                        "enabled": True,
                        "description": tool.description or "MCP tool from Claude config",
                        "syntax": syntax
                    }
                print(f"Loaded MCP server '{server_name}' with {len(tools_response.tools)} tools.")

    def closeEvent(self, event):
        asyncio.get_event_loop().run_until_complete(self.lifespan_stack.aclose())
        super().closeEvent(event)

    def on_load_finished(self, ok):
        if ok:
            print("Page loaded successfully. Injecting JavaScript v4.3...")
            self.inject_javascript()
    
    def inject_javascript(self):
        js_files = ["qwebchannel.js", "grok_automator.js"]
        for js_file in js_files:
            try:
                with open(js_file, "r", encoding="utf-8") as f:
                    js_code = f.read()
                    self.browser.page().runJavaScript(js_code)
            except FileNotFoundError:
                print(f"ERROR: {js_file} not found.")
                return
            
    def send_text_to_grok(self, text):
        json_escaped_text = json.dumps(text)
        js_code = f"""
            (function() {{
                let chat_input = document.querySelector('textarea[aria-label="Ask Grok anything"]');
                let form = chat_input ? chat_input.closest('form') : null;
                let send_button = form ? form.querySelector('button[type="submit"]') : null;
                if(chat_input && send_button) {{
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeInputValueSetter.call(chat_input, {json_escaped_text});
                    const event = new Event('input', {{ bubbles: true }});
                    chat_input.dispatchEvent(event);
                    setTimeout(() => {{
                        if (!send_button.disabled) {{ send_button.click(); }}
                    }}, 100);
                }}
            }})();
        """
        self.browser.page().runJavaScript(js_code)
        
    def send_tool_output_to_grok(self, output):
        self.send_text_to_grok(f"[Tool Output]:\n```\n{output}\n```")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = GrokExcess()
    main_window.show()
    sys.exit(app.exec())