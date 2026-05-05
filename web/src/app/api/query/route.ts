import { NextRequest, NextResponse } from "next/server";

import { parseKeyValueOutput, runCliCommand } from "@/lib/backend";
import type { QueryApiResponse } from "@/lib/types";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { question?: string; showCypher?: boolean };
  const question = (body.question || "").trim();
  const showCypher = Boolean(body.showCypher);

  if (!question) {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }

  const args = ["query", "--question", question];
  if (showCypher) {
    args.push("--show-cypher");
  }

  const result = await runCliCommand(args);
  const parsed = parseKeyValueOutput(result.stdout);
  const evidenceRaw = parsed.evidence || "[]";

  let evidence: Array<Record<string, unknown>> = [];
  try {
    evidence = JSON.parse(evidenceRaw) as Array<Record<string, unknown>>;
  } catch {
    evidence = [];
  }

  const payload: QueryApiResponse = {
    queryId: parsed.query_id || "",
    answer: parsed.answer || "",
    evidenceRows: Number(parsed.evidence_rows || evidence.length || 0),
    evidence,
    cypher: parsed.cypher,
    warnings: parsed.warnings ? parsed.warnings.split(";").map((x) => x.trim()).filter(Boolean) : [],
    rawOutput: result.stdout
  };

  if (result.exitCode !== 0) {
    return NextResponse.json({ ...payload, error: result.stderr || "query command failed" }, { status: 500 });
  }

  return NextResponse.json(payload);
}
