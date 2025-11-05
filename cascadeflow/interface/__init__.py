"""
cascadeflow Interface Module
============================

User-facing interface components for visual feedback and UI.

Current Components:
-------------------
- VisualConsumer: Base visual feedback system
- TerminalVisualConsumer: Terminal streaming with indicators
- SilentConsumer: No-output consumer for testing

Future Extensions:
------------------
- TerminalUI: Enhanced terminal with Rich formatting
  - Progress bars, tables, live updates
  - Color schemes, themes
  - ASCII art, spinners

- JupyterUI: Jupyter notebook widgets
  - IPython display integration
  - Interactive widgets
  - Plotly/Matplotlib charts
  - Real-time metrics

- WebUI: Web dashboard interface
  - FastAPI/Flask endpoints
  - WebSocket streaming
  - React/Vue components
  - REST API

- Formatters: Output formatting
  - JSON exporter
  - Markdown formatter
  - CSV exporter
  - HTML reports

Usage:
------
```python
from cascadeflow.interface import TerminalVisualConsumer

# Create consumer
consumer = TerminalVisualConsumer(enable_visual=True)

# Use with agent
result = await agent.run_streaming(query)
```
"""

from .visual_consumer import (
    SilentConsumer,
    TerminalVisualConsumer,
)

__all__ = [
    "TerminalVisualConsumer",
    "SilentConsumer",
]

__version__ = "2.2.0"
