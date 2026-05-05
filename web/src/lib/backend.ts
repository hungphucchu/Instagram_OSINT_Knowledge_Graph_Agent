import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(process.cwd(), "..");
const repoVenvPython = path.join(repoRoot, "tf-env-310", "bin", "python");
const pythonCandidates = [
  process.env.BACKEND_PYTHON,
  fs.existsSync(repoVenvPython) ? repoVenvPython : undefined,
  "python",
  "python3"
].filter(Boolean) as string[];

type CliRun = { stdout: string; stderr: string; exitCode: number };

function runWithPython(pythonBin: string, args: string[]): Promise<CliRun> {
  return new Promise((resolve) => {
    const child = spawn(pythonBin, ["-m", "cli", ...args], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONPATH: path.join(repoRoot, "src") }
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (err) => {
      resolve({ stdout, stderr: `${stderr}\n${String(err)}`.trim(), exitCode: 127 });
    });
    child.on("close", (code) => {
      resolve({ stdout, stderr, exitCode: code ?? 1 });
    });
  });
}

export async function runCliCommand(args: string[]): Promise<CliRun> {
  let last: CliRun = { stdout: "", stderr: "No python executable configured", exitCode: 127 };
  for (const bin of pythonCandidates) {
    last = await runWithPython(bin, args);
    if (last.exitCode !== 127) {
      return last;
    }
  }
  return last;
}

export function parseKeyValueOutput(output: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of output.split("\n")) {
    const idx = line.indexOf("=");
    if (idx <= 0) {
      continue;
    }
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    out[key] = value;
  }
  return out;
}
