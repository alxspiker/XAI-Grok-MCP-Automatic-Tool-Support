import sys
import os
import json
import re
import platform
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from collections.abc import AsyncIterator
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QMainWindow, QMenuBar, QScrollArea, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, QDir, pyqtSlot, QObject, Qt
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

    @pyqtSlot(str, bool)
    def set_tool_enabled(self, tool_name, enabled):
        if tool_name in self.main_window.tools:
            self.main_window.tools[tool_name]["enabled"] = enabled
            print(f"Set tool '{tool_name}' enabled state to: {enabled}")

    @pyqtSlot()
    def send_initial_system_prompt(self):
        os_name = platform.system()
        os_info = f"You are operating on a **{os_name}** system."
        tool_instructions = [f"### {name}\n- **Description**: {details['description']}\n- **Syntax**: `{details['syntax']}`"
                            for name, details in self.main_window.tools.items() if details.get("enabled")]
        
        full_prompt = (
            "**[AGENT PROTOCOL INITIATED]**\n\n"
            "1. **Persona**: You are Grok Excess, a helpful and autonomous AI agent.\n"
            "2. **Environment**: " + os_info + "\n"
            "3. **Core Directive**: Autonomously think, act, observe, and repeat until the task is complete.\n"
            "4. **Available Tools**:\n" + "\n".join(tool_instructions) + "\n\n"
            "To use a tool, you **MUST** respond with **ONLY** a single complete tool command in plain text outside of any code blocks. Do not include any other text or explanations.\n"
            "Acknowledge this protocol and await your first task."
        )
        self.main_window.send_text_to_grok(full_prompt)

class GrokExcess(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Grok Excess - Agent Mode")
        self.setGeometry(100, 100, 1200, 800)
        self.tools = {}
        self.mcp_clients = {}
        self.mcp_processes = {}
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
        self.setup_menu()

    def setup_menu(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Settings')
        open_settings_action = QAction('Open Tool Settings', self)
        open_settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(open_settings_action)

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Tool Settings')
        dialog.resize(500, 600)

        main_layout = QVBoxLayout(dialog)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)

        from collections import defaultdict
        groups = defaultdict(list)
        for tool_name in sorted(self.tools):
            parts = tool_name.split('_', 2)
            if len(parts) == 3 and parts[0] == 'MCP':
                server = parts[1]
                groups[server].append({
                    'full_name': tool_name,
                    'short_name': parts[2],
                    'enabled': self.tools[tool_name]['enabled'],
                    'description': self.tools[tool_name]['description']
                })

        for server in sorted(groups):
            group_box = QGroupBox()
            group_box_layout = QVBoxLayout()
            group_box_layout.setContentsMargins(0, 5, 0, 5)
            group_box_layout.setSpacing(5)

            master_checkbox = QCheckBox(server.replace('-', ' ').title())
            master_checkbox.setTristate(True)

            tools_layout = QVBoxLayout()
            tools_layout.setContentsMargins(20, 0, 0, 0)

            child_checkboxes = []
            enabled_count = 0

            for tool in sorted(groups[server], key=lambda t: t['short_name']):
                cb = QCheckBox(tool['short_name'])
                cb.setChecked(tool['enabled'])
                cb.setToolTip(tool['description'])
                if tool['enabled']:
                    enabled_count += 1
                tools_layout.addWidget(cb)
                child_checkboxes.append({'widget': cb, 'name': tool['full_name']})

            if enabled_count == 0:
                master_checkbox.setCheckState(Qt.CheckState.Unchecked)
            elif enabled_count == len(child_checkboxes):
                master_checkbox.setCheckState(Qt.CheckState.Checked)
            else:
                master_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)

            def on_master_toggled(state, master_cb=master_checkbox, cbs=child_checkboxes):
                if master_cb.isTristate():
                    master_cb.setTristate(False)
                new_state = master_cb.isChecked()
                for child_info in cbs:
                    child_info['widget'].blockSignals(True)
                    child_info['widget'].setChecked(new_state)
                    child_info['widget'].blockSignals(False)
                    self.js_api.set_tool_enabled(child_info['name'], new_state)

            def on_child_toggled(state, master_cb=master_checkbox, cbs=child_checkboxes):
                enabled_count = sum(1 for child_info in cbs if child_info['widget'].isChecked())
                master_cb.blockSignals(True)
                if enabled_count == 0:
                    master_cb.setCheckState(Qt.CheckState.Unchecked)
                elif enabled_count == len(cbs):
                    master_cb.setCheckState(Qt.CheckState.Checked)
                else:
                    master_cb.setTristate(True)
                    master_cb.setCheckState(Qt.CheckState.PartiallyChecked)
                master_cb.blockSignals(False)
            
            master_checkbox.clicked.connect(on_master_toggled)

            for child_info in child_checkboxes:
                child_info['widget'].stateChanged.connect(
                    lambda state, fn=child_info['name'], handler=on_child_toggled: (
                        self.js_api.set_tool_enabled(fn, bool(state)),
                        handler(state)
                    )
                )

            group_box_layout.addWidget(master_checkbox)
            group_box_layout.addLayout(tools_layout)
            group_box.setLayout(group_box_layout)
            container_layout.addWidget(group_box)

        container_layout.addStretch()
        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        main_layout.addWidget(button_box)

        dialog.exec()

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
                # *** THIS IS THE CORRECTED LINE ***
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