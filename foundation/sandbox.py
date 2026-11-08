"""E2B-only execution primitive. No host code execution or filesystem mounts."""
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class SandboxLimits:
    template_id:str
    memory_mb:int
    timeout_seconds:int=60
    output_bytes:int=64000
    def validate(self):
        if not isinstance(self.template_id,str) or not self.template_id.strip():raise ValueError('Reviewed E2B template required')
        if type(self.memory_mb)!=int or not 128<=self.memory_mb<=4096:raise ValueError('Reviewed template memory limit required')
        if type(self.timeout_seconds)!=int or not 1<=self.timeout_seconds<=60:raise ValueError('Timeout must be 1–60 seconds')
        if type(self.output_bytes)!=int or not 1<=self.output_bytes<=64000:raise ValueError('Output budget exceeds policy')


def execute_python(code,limits,factory=None):
    limits.validate()
    if not isinstance(code,str) or not code.strip() or len(code.encode())>20000:raise ValueError('Bounded Python source required')
    if factory is None:
        from e2b_code_interpreter import Sandbox
        factory=Sandbox
    # Memory is provisioned on the reviewed template; this declaration alone
    # cannot prove the live template's actual resources. Release needs attestation.
    sandbox=factory.create(template=limits.template_id,timeout=limits.timeout_seconds,allow_internet_access=False)
    try:
        result=sandbox.run_code(code,timeout=limits.timeout_seconds)
        if result.error:raise RuntimeError('Sandbox execution failed')
        output={'stdout':list(result.logs.stdout),'stderr':list(result.logs.stderr)}
        if len(json.dumps(output,ensure_ascii=False).encode())>limits.output_bytes:raise ValueError('Sandbox output exceeds budget')
        return output
    finally:sandbox.kill()
