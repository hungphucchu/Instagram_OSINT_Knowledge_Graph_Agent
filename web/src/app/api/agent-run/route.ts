import { NextRequest, NextResponse } from "next/server";

import { runCliCommand } from "@/lib/backend";
import type { AgentRunRequest, AgentRunResponse } from "@/lib/types";

function buildArgs(body: AgentRunRequest): string[] {
  const args: string[] = [body.command];
  if (body.runId) {
    args.push("--run-id", body.runId);
  }
  if (typeof body.maxItems === "number") {
    args.push("--max-items", String(body.maxItems));
  }
  if (body.usernames && body.usernames.length > 0) {
    for (const username of body.usernames) {
      if (username.trim()) {
        args.push("--username", username.trim().replace(/^@/, ""));
      }
    }
  }
  if (body.command === "query" && body.question) {
    args.push("--question", body.question);
    if (body.showCypher) {
      args.push("--show-cypher");
    }
  }
  return args;
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as AgentRunRequest;
  if (!body.command) {
    return NextResponse.json({ error: "command is required" }, { status: 400 });
  }

  const args = buildArgs(body);
  const result = await runCliCommand(args);

  const payload: AgentRunResponse = {
    ok: result.exitCode === 0,
    command: body.command,
    stdout: result.stdout,
    stderr: result.stderr,
    exitCode: result.exitCode
  };

  const status = payload.ok ? 200 : 500;
  return NextResponse.json(payload, { status });
}
