---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

Explain what this Python function does:

```python
def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]
```
