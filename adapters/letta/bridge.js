import readline from "node:readline";
import { LettaAgentClient } from "@letta-ai/letta-agent-sdk";

const url = process.env.MARCIANA_LETTA_URL ?? "http://127.0.0.1:4500";
const model = process.env.MARCIANA_LETTA_MODEL ?? "ollama/llama3.1:latest";
const authToken = process.env.MARCIANA_LETTA_TOKEN ?? "benchmark-local-token";
const agents = new Map();

function newClient() {
  return new LettaAgentClient({
    backend: "remote",
    url,
    ...(authToken ? { authToken } : {}),
    requestTimeoutMs: 600_000,
  });
}

const systemPrompt = `You are a memory agent under evaluation. Use your memory
tool to persist every fact the user asks you to remember. Stored facts contain
bounded benchmark IDs in the form [id:VALUE]; preserve those markers exactly.
For recall requests, inspect your persistent memory and answer with only a JSON
array of matching benchmark IDs, best match first. Never return prose, facts,
or IDs that are not present in your memory.`;

async function agentFor(principal) {
  if (!agents.has(principal)) {
    const client = newClient();
    const agentId = await client.createAgent({
      name: `marciana-${principal}-${Date.now()}`,
      model,
      systemPrompt,
      memfs: true,
      baseTools: ["memory"],
      permissionMode: "acceptEdits",
    });
    agents.set(principal, agentId);
  }
  return agents.get(principal);
}

async function turn(agentId, prompt) {
  const client = newClient();
  const result = await client.prompt(prompt, agentId, {
    permissionMode: "acceptEdits",
  });
  if (!result.success) throw new Error(result.errorDetail ?? result.error ?? result.errorCode);
  return result.result ?? "";
}

function idsFrom(text) {
  const match = text.match(/\[[\s\S]*?\]/);
  if (!match) return [];
  const parsed = JSON.parse(match[0]);
  if (!Array.isArray(parsed)) throw new Error("recall response is not an array");
  return parsed.filter((value) => typeof value === "string").slice(0, 8);
}

async function handle(request) {
  if (request.op === "info") {
    return { version: `agent-sdk-0.6.2/app-server/${model}` };
  }
  if (request.op === "reset") {
    for (const agentId of agents.values()) await newClient().agents.delete(agentId);
    agents.clear();
    return { ok: true };
  }
  if (request.op === "remember") {
    const agentId = await agentFor(request.principal);
    const interval = request.valid_from || request.valid_until
      ? ` Valid from ${request.valid_from ?? "unspecified"} through ${request.valid_until ?? "open-ended"}.`
      : "";
    await turn(agentId, `Remember this durable fact exactly: [id:${request.memory_id}] ${request.text}.${interval}`);
    return { ok: true };
  }
  if (request.op === "recall") {
    const agentId = await agentFor(request.principal);
    const asOf = request.as_of ? ` Answer as of ${request.as_of}.` : "";
    const prompt = request.query === "" ? "" :
      `Recall memories relevant to this query: ${JSON.stringify(request.query)}.${asOf} Return only a JSON array of [id:...] values without the id: prefix.`;
    const answer = await turn(agentId, prompt);
    return { ids: idsFrom(answer) };
  }
  if (request.op === "forget") {
    const agentId = await agentFor(request.principal);
    await turn(agentId, `Permanently delete the memory with marker [id:${request.memory_id}]. Confirm only after using your memory tool.`);
    return { ok: true };
  }
  if (request.op === "restart") {
    // A fresh SDK transport is already used for every operation; persistent
    // state remains in the App Server and MemFS.
    return { ok: true };
  }
  throw new Error(`unknown operation: ${request.op}`);
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  try {
    const response = await handle(JSON.parse(line));
    process.stdout.write(`${JSON.stringify(response)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ error: String(error?.message ?? error) })}\n`);
  }
}
process.exit(0);
