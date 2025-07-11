// grok_automator.js v4.4 - Robust Parsing

(function() {
    'use strict';

    if (window.grokAutomator) {
        return;
    }
    window.grokAutomator = { initialized: true };

    let backend;
    new QWebChannel(qt.webChannelTransport, function (channel) {
        backend = channel.objects.backend;
        console.log("Grok Excess: Python backend connected.");
        init();
    });

    function injectCSS() {
        if (document.getElementById('grok-excess-styles')) return;
        const css = `
            #send-instructions-btn {
                border: 1px solid #1e88e5; color: #1e88e5; background: transparent;
                padding: 8px 15px; border-radius: 20px; cursor: pointer;
                font-size: 14px; margin: 10px auto; display: block;
            }
            #send-instructions-btn:hover { background-color: rgba(30, 136, 229, 0.1); }
        `;
        const styleSheet = document.createElement("style");
        styleSheet.id = 'grok-excess-styles';
        styleSheet.innerText = css;
        document.head.appendChild(styleSheet);
    }

    function processLastMessage() {
        // Find the last message bubble from the AI.
        const allBubbles = document.querySelectorAll('.message-bubble');
        const lastReplyContainer = allBubbles[allBubbles.length - 1];
        
        if (!lastReplyContainer || lastReplyContainer.dataset.grokExcessProcessed === 'true') {
            return;
        }

        let command_to_run = null;
        const command_regex = /\[use_tool:[\s\S]*?\]/g; // Find all [use_tool:...] blocks

        // Priority 1: Look for commands inside markdown code blocks (`<pre><code>...</code></pre>`).
        const codeBlocks = lastReplyContainer.querySelectorAll('pre code');
        if (codeBlocks.length > 0) {
            const lastCodeBlockText = codeBlocks[codeBlocks.length - 1].innerText;
            const matches = lastCodeBlockText.match(command_regex);
            if (matches && matches.length > 0) {
                command_to_run = matches[matches.length - 1]; // Get the last command found
            }
        }

        // Priority 2: Fallback for when the AI fails to use a code block.
        if (!command_to_run) {
            const allText = lastReplyContainer.innerText || lastReplyContainer.textContent;
            const matches = allText.match(command_regex);
            if (matches && matches.length > 0) {
                command_to_run = matches[matches.length - 1]; // Get the last command found
            }
        }
        
        if (command_to_run) {
            console.log("Grok Excess: Detected tool command:", command_to_run);
            
            // Mark the entire message bubble as processed to avoid re-triggering.
            lastReplyContainer.dataset.grokExcessProcessed = 'true'; 
            
            if (backend) {
                backend.tool_triggered(command_to_run);
            }
        }
    }

    function init() {
        if (!backend) {
            console.error("Grok Excess: Backend not available.");
            return;
        }

        injectCSS();
        
        const observer = new MutationObserver(processLastMessage);
        const interval = setInterval(() => {
            const chatContainer = document.querySelector('div[style*="overflow-anchor: none;"]');
            if (chatContainer) {
                observer.observe(chatContainer, { childList: true, subtree: true, characterData: true });
                console.log("Grok Excess: Command observer is now active.");
                clearInterval(interval);
            }
        }, 1000);

        setInterval(screenCheck, 1500);
    }
    
    function screenCheck() {
        const isOnWelcomeScreen = !!document.querySelector('svg[width="320"]');
        const buttonExists = !!document.getElementById("send-instructions-btn");

        if (isOnWelcomeScreen && !buttonExists) {
            addSendInstructionsButton();
        } else if (!isOnWelcomeScreen && buttonExists) {
            document.getElementById("send-instructions-btn")?.remove();
        }
    }
    
    function addSendInstructionsButton() {
        const targetContainer = document.querySelector(".flex.flex-col-reverse.items-center");
        if (targetContainer) {
            const button = document.createElement("button");
            button.id = "send-instructions-btn";
            button.textContent = "Initialize Grok Agent";
            button.onclick = () => {
                if (backend) backend.send_initial_system_prompt();
            };
            targetContainer.prepend(button);
        }
    }

})();