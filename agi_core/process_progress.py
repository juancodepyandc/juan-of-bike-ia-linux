"""Bounded real engine telemetry after the diagnostic output budget is exhausted."""
import time


class EngineProgress:
    def __init__(self, interval_seconds=1., line_chars=512):
        self.interval=interval_seconds;self.limit=line_chars
        self.line='';self.pending=None;self.emitted=None;self.last_emit=float('-inf')

    def feed(self, text, *, now=None, final=False):
        for fragment in text.splitlines(keepends=True):
            self.line=(self.line+fragment)[:self.limit]
            if fragment.endswith(('\n','\r')):
                value=self.line.rstrip('\r\n')
                if value.startswith(('PROGRESS:','SCENE_ORCH:')):self.pending=value
                self.line=''
        if final and self.line:
            if self.line.startswith(('PROGRESS:','SCENE_ORCH:')):self.pending=self.line
            self.line=''
        current=time.monotonic() if now is None else now
        if self.pending and self.pending!=self.emitted and (final or current-self.last_emit>=self.interval):
            value=self.pending;self.emitted=value;self.pending=None;self.last_emit=current
            return value
        return None
