import unittest
from unittest.mock import Mock
from types import SimpleNamespace as Obj
from foundation.sandbox import execute_python,SandboxLimits
class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.factory=Mock();self.sandbox=self.factory.create.return_value
        self.sandbox.run_code.return_value=Obj(error=None,logs=Obj(stdout=['ok'],stderr=[]))
        self.limits=SandboxLimits('reviewed-template',512)
    def test_isolated_execution_and_cleanup(self):
        self.assertEqual(execute_python('print(1)',self.limits,self.factory)['stdout'],['ok'])
        self.factory.create.assert_called_once_with(template='reviewed-template',timeout=60,allow_internet_access=False)
        self.sandbox.run_code.assert_called_once_with('print(1)',timeout=60);self.sandbox.kill.assert_called_once()
    def test_timeout_still_kills(self):
        self.sandbox.run_code.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):execute_python('print(1)',self.limits,self.factory)
        self.sandbox.kill.assert_called_once()
    def test_output_cap_still_kills(self):
        self.sandbox.run_code.return_value.logs.stdout=['x'*65000]
        with self.assertRaises(ValueError):execute_python('print(1)',self.limits,self.factory)
        self.sandbox.kill.assert_called_once()
    def test_invalid_limits_never_create_remote(self):
        with self.assertRaises(ValueError):execute_python('print(1)',SandboxLimits('template',512,300),self.factory)
        self.factory.create.assert_not_called()
