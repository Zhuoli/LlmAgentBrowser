# Browser Automation Design: Chrome Extension Approaches

## Problem Statement

Current browser automation solutions like `browser-use` and `chrome-devtools-mcp` require **closing all Chrome windows** before running because they launch a new Chrome instance with the user's profile. This is disruptive to the user's workflow.

**Goal**: Enable LLM-powered browser automation that works with the **already-running Chrome browser**, preserving:
- Existing login sessions (Twitter, Gmail, etc.)
- Open tabs and windows
- User's browsing context

---

## Solution Comparison

| Feature | chrome-devtools-mcp | Browser MCP | Chrome MCP Server | Manus-style |
|---------|---------------------|-------------|-------------------|-------------|
| Close Chrome required | **Yes** | **No** | **No** | **No** |
| Architecture | Launches new Chrome | Extension + MCP | Extension + MCP | Extension + WebSocket |
| Uses existing logins | Yes (but must close) | **Yes** | **Yes** | **Yes** |
| Bot detection | May trigger | Avoids | Avoids | Avoids |
| MCP Protocol | Yes | Yes | Yes | No (custom WebSocket) |
| Open Source | Yes | Yes | Yes | No |
| Tools count | 26 | 12 | 20+ | N/A |

---

## Solution 1: Browser MCP

**Repository**: https://github.com/BrowserMCP/mcp
**Chrome Extension**: [Chrome Web Store](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)
**Documentation**: https://docs.browsermcp.io/

### Architecture

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   LLM Client    │◄────────────────────►│  MCP Server     │
│ (Claude/Cursor) │                       │ (npx @browsermcp)│
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          Chrome Extension API
                                                   │
                                          ┌────────▼────────┐
                                          │ Browser MCP     │
                                          │ Chrome Extension│
                                          └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │ Running Chrome  │
                                          │ (existing tabs) │
                                          └─────────────────┘
```

### Setup

1. **Install Chrome Extension**
   ```
   Chrome Web Store → "Browser MCP"
   ```

2. **Configure MCP Server** (for Claude Desktop, Cursor, etc.)
   ```json
   {
     "mcpServers": {
       "browsermcp": {
         "command": "npx",
         "args": ["@browsermcp/mcp@latest"]
       }
     }
   }
   ```

### Available Tools (12)

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to a URL |
| `browser_go_back` | Go back in history |
| `browser_go_forward` | Go forward in history |
| `browser_click` | Click an element |
| `browser_type` | Type text into an element |
| `browser_press_key` | Press a keyboard key |
| `browser_drag` | Drag and drop |
| `browser_hover` | Hover over an element |
| `browser_snapshot` | Get page accessibility snapshot |
| `browser_screenshot` | Take a screenshot |
| `browser_console_logs` | Get console logs |
| `browser_wait` | Wait for a duration |

### Pros
- Simple setup (just npx + extension)
- Well-documented
- Active development (5.4k GitHub stars)
- Works with Claude Desktop, Cursor, VS Code, Windsurf

### Cons
- Fewer tools than Chrome MCP Server
- No semantic search capability
- Core MCP code not buildable standalone (monorepo dependency)

---

## Solution 2: Chrome MCP Server (mcp-chrome)

**Repository**: https://github.com/hangwin/mcp-chrome
**License**: MIT

### Architecture

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   LLM Client    │◄────────────────────►│ mcp-chrome-bridge│
│ (Claude/Cursor) │    (HTTP/Streamable)  │  (Node.js)      │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          Native Messaging
                                                   │
                                          ┌────────▼────────┐
                                          │ Chrome MCP      │
                                          │ Extension       │
                                          └────────┬────────┘
                                                   │
                                          Chrome Extension APIs
                                          (tabs, debugger, etc.)
                                                   │
                                          ┌────────▼────────┐
                                          │ Running Chrome  │
                                          │ (existing tabs) │
                                          └─────────────────┘
```

### Setup

1. **Install the bridge globally**
   ```bash
   npm install -g mcp-chrome-bridge
   ```

2. **Download and load extension**
   - Download from [GitHub Releases](https://github.com/hangwin/mcp-chrome/releases)
   - Go to `chrome://extensions/`
   - Enable Developer mode
   - Click "Load unpacked" → select extension folder

3. **Configure MCP** (Streamable HTTP - Recommended)
   ```json
   {
     "mcpServers": {
       "chrome-mcp-server": {
         "type": "streamableHttp",
         "url": "http://127.0.0.1:12306/mcp"
       }
     }
   }
   ```

### Available Tools (20+)

| Category | Tools |
|----------|-------|
| **Browser Management** | Tab control, window management, navigation |
| **Screenshots** | Full-page, element-level, custom dimensions |
| **Network** | Request monitoring, custom HTTP requests |
| **Content Analysis** | Semantic search across tabs, content extraction |
| **Interaction** | Click, form fill, keyboard simulation |
| **Data** | History search, bookmark operations |

### Pros
- Most feature-rich (20+ tools)
- Semantic search across tabs
- Network monitoring capabilities
- Full Chrome Extension API access

### Cons
- More complex setup (bridge + extension)
- Requires manual extension loading (not on Chrome Web Store)

---

## Solution 3: Manus-style Architecture (Custom Implementation)

**Reference**: Manus Browser Operator
**Key Technology**: `chrome.debugger` API

### Architecture

```
┌─────────────────┐                       ┌─────────────────┐
│   LLM Backend   │◄─────WebSocket───────►│ Background.js   │
│  (Your Server)  │     (bidirectional)   │ (Service Worker)│
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          chrome.debugger API
                                          (CDP over extension)
                                                   │
                                          ┌────────▼────────┐
                                          │ Target Tab      │
                                          │ (any open tab)  │
                                          └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │ Content Script  │
                                          │ (DOM access)    │
                                          └─────────────────┘
```

### Key Insight: `chrome.debugger` API vs `--remote-debugging-port`

| Feature | `--remote-debugging-port` | `chrome.debugger` API |
|---------|---------------------------|----------------------|
| **Setup** | Command-line flag on launch | Chrome Extension |
| **Profile Lock** | Yes (requires closed profile) | **No** |
| **User Warning** | None | Visible warning bar |
| **Scope** | Entire browser instance | **Specific tabs only** |
| **Auth State** | Fresh session | **Inherits existing logins** |

### Implementation Components

1. **manifest.json** - Extension permissions
   ```json
   {
     "permissions": [
       "debugger",
       "tabs",
       "activeTab",
       "scripting"
     ]
   }
   ```

2. **background.js** - Service worker
   - Maintains WebSocket connection to LLM backend
   - Translates commands to `chrome.debugger.sendCommand()` calls
   - Orchestrates tab control

3. **content.js** - Content script
   - Injected into web pages
   - DOM manipulation and data extraction
   - Can use libraries like Readability.js, Turndown.js

### `chrome.debugger` API Capabilities

```javascript
// Attach to a tab
chrome.debugger.attach({ tabId: tabId }, "1.3", callback);

// Send CDP commands
chrome.debugger.sendCommand(
  { tabId: tabId },
  "Input.dispatchMouseEvent",
  { type: "mousePressed", x: 100, y: 200, button: "left" }
);

// Available CDP domains:
// - Input: mouse, keyboard, touch events
// - DOM: inspect/modify DOM
// - CSS: inspect/modify styles
// - Network: monitor/intercept requests
// - Page: navigation, screenshots
// - Runtime: execute JavaScript
```

### Pros
- Full CDP access (most powerful)
- Complete control over implementation
- Can integrate with any backend (not limited to MCP)
- Tab-level granularity

### Cons
- Requires building custom extension
- More development effort
- User sees "debugging" warning bar
- Security considerations (powerful permissions)

---

## Recommendation

### For Quick Integration: **Browser MCP** (Solution 1)

Best for: Getting started quickly with existing MCP clients

```bash
# One command to start
npx @browsermcp/mcp@latest
```

### For Advanced Features: **Chrome MCP Server** (Solution 2)

Best for: Need semantic search, network monitoring, or extensive automation

### For Custom Solutions: **Manus-style** (Solution 3)

Best for: Building a production system with custom requirements

---

## Implementation Plan for This Project

### Phase 1: Browser MCP Integration
1. Install Browser MCP Chrome extension
2. Create `twitter_fetcher_browsermcp.py` that connects via MCP
3. Test tweet fetching with existing Twitter login

### Phase 2: Performance Comparison
| Metric | browser-use | chrome-devtools-mcp | Browser MCP |
|--------|-------------|---------------------|-------------|
| Setup friction | Close Chrome | Close Chrome | None |
| Execution time | TBD | TBD | TBD |
| Reliability | TBD | TBD | TBD |

### Phase 3: (Optional) Custom Extension
If Browser MCP doesn't meet requirements, build custom extension using Manus-style architecture with `chrome.debugger` API.

---

## References

- [Browser MCP](https://browsermcp.io/)
- [Chrome MCP Server](https://github.com/hangwin/mcp-chrome)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [chrome.debugger API](https://developer.chrome.com/docs/extensions/reference/debugger/)
- [Manus Browser Operator Analysis](https://mindgard.ai/blog/manus-rubra-full-browser-remote-control)
