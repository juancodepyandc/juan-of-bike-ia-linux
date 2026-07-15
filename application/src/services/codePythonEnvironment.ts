import { isWindows } from './codeSandboxRuntime.ts'

export const AURORA_PYTHON_ENV_DIR = 'aurora-python-env'

export function auroraPythonExecutable(): string {
  return isWindows()
    ? `${AURORA_PYTHON_ENV_DIR}\\Scripts\\python.exe`
    : `${AURORA_PYTHON_ENV_DIR}/bin/python`
}
