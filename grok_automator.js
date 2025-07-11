// grok_automator.js v4.2 - UI Integration

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

    // We only need CSS for the modal now, as the button will use native classes.
    function injectCSS() {
        if (document.getElementById('grok-excess-styles')) return;
        const css = `
            #grok-excess-modal {
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background-color: rgba(0,0,0,0.6); z-index: 10000;
                display: none; align-items: center; justify-content: center;
            }
            #grok-excess-modal-content {
                background-color: #2c2c2c; color: white; padding: 25px;
                border-radius: 12px; width: 90%; max-width: 500px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.5);
            }
            #grok-excess-modal h2 { margin-top: 0; }
            #grok-excess-modal .tool-item { display: flex; align-items: center; margin-bottom: 15px; font-size: 16px; }
            #grok-excess-modal .tool-item input { margin-right: 12px; width:18px; height:18px; }
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
    
    // --- NEW FUNCTION to inject the button into the native UI ---
    function injectAgentButton() {
        // Use an interval to wait for the target container to load
        const injectionInterval = setInterval(() => {
            // This is the div that contains the "Share" button etc.
            const targetContainer = document.querySelector('div.absolute.flex.flex-row.items-center.gap-0\\.5.ms-auto.end-3');
            
            // Check if the container exists and if our button isn't already there
            if (targetContainer && !document.getElementById('grok-excess-agent-btn')) {
                clearInterval(injectionInterval); // Stop polling once found

                const agentBtn = document.createElement('button');
                agentBtn.id = 'grok-excess-agent-btn';
                
                // Use the same classes as the "Share" button for a native look, but with a different color
                agentBtn.className = "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium leading-[normal] cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60 disabled:cursor-not-allowed transition-colors duration-100 select-none border border-blue-500 text-blue-400 hover:bg-blue-500/20 h-10 px-3.5 py-2 rounded-full";
                
                // Add an icon and text
                agentBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-bot"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg><span class="font-semibold">Agent</span>`;
                
                agentBtn.onclick = toggleToolsModal;
                
                // Prepend it to the container so it appears on the left of the existing buttons
                targetContainer.prepend(agentBtn);
                console.log("Grok Excess: Agent button injected into top bar.");
            }
        }, 500);
    }
    
    function processLastMessage() {
        const lastReplyContainer = document.getElementById('last-reply-container');
        if (!lastReplyContainer) return;

        const messageParagraphs = lastReplyContainer.querySelectorAll('.response-content-markdown p');
        if (!messageParagraphs) return;
        
        for (const p of messageParagraphs) {
            if (p.dataset.grokExcessProcessed === 'true') continue;

            const messageText = (p.innerText || p.textContent);
            const toolCommandMatch = messageText.match(/(\[use_tool:.*?\])/);

            if (toolCommandMatch) {
                const command = toolCommandMatch[0];
                console.log("Grok Excess: Detected tool command:", command);
                p.dataset.grokExcessProcessed = 'true';
                if (backend) backend.tool_triggered(command);
                break; 
            }
        }
    }

    // --- Main Initialization ---
    function init() {
        if (!backend) {
            console.error("Grok Excess: Backend not available.");
            return;
        }

        injectCSS();
        injectAgentButton(); // Call the new button injection function
        createToolsModal(); // Create the modal, but keep it hidden
        
        const observer = new MutationObserver(processLastMessage);
        const interval = setInterval(() => {
            const chatContainer = document.querySelector('div[style*="overflow-anchor: none;"]');
            if (chatContainer) {
                observer.observe(chatContainer, { childList: true, subtree: true, characterData: true });
                console.log("Grok Excess: Final observer is now active.");
                clearInterval(interval);
            }
        }, 1000);

        setInterval(screenCheck, 1500);
    }
    
    // --- UI Helper Functions ---
    function screenCheck(){const e=!!document.querySelector('svg[width="320"]'),t=!!document.getElementById("send-instructions-btn");e&&!t?addSendInstructionsButton():e||!t||document.getElementById("send-instructions-btn")?.remove()}function addSendInstructionsButton(){const e=document.querySelector(".flex.flex-col-reverse.items-center");if(e){const t=document.createElement("button");t.id="send-instructions-btn",t.textContent="Initialize Grok Agent",t.onclick=()=>{backend&&backend.send_initial_system_prompt()},e.prepend(t)}}function createToolsModal(){if(document.getElementById("grok-excess-modal"))return;const e=document.createElement("div");e.id="grok-excess-modal",e.innerHTML='<div id="grok-excess-modal-content"><h2>Manage Tools</h2><div id="grok-tools-list">Loading...</div></div>',e.onclick=e=>{"grok-excess-modal"===e.target.id&&toggleToolsModal()},document.body.appendChild(e)}function toggleToolsModal(){const e=document.getElementById("grok-excess-modal"),t="none"===e.style.display;t?(e.style.display="flex",backend.get_tools(e=>{const t=JSON.parse(e),o=document.getElementById("grok-tools-list");for(const e in o.innerHTML="",t){const s=t[e],n=document.createElement("div");n.className="tool-item";const c=document.createElement("input");c.type="checkbox",c.id=`tool-checkbox-${e}`,c.checked=s.enabled,c.onchange=()=>backend.set_tool_enabled(e,c.checked);const d=document.createElement("label");d.htmlFor=c.id,d.textContent=e,n.appendChild(c),n.appendChild(d),o.appendChild(n)}})):e.style.display="none"}

})();