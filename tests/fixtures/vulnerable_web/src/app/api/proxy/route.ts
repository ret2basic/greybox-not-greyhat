import { exec } from "node:child_process";

export async function POST(req: Request) {
  const body = await req.json();
  const target = body.url;
  const { command, next } = body;
  const upstream = await fetch(target);
  exec(command);
  return Response.redirect(next + upstream.status);
}
