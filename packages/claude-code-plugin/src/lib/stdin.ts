export interface HookInput {
  session_id: string;
  prompt?: string;
  transcript_path?: string;
}

export interface HookOutput {
  continue?: boolean;
  hookSpecificOutput?: {
    hookEventName: string;
    additionalContext?: string;
  };
}

export function readStdin(): Promise<HookInput> {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      try {
        resolve(data.trim() ? JSON.parse(data) : {});
      } catch (err) {
        reject(new Error(`Failed to parse stdin JSON: ${(err as Error).message}`));
      }
    });
    process.stdin.on("error", reject);
    if (process.stdin.isTTY) resolve({} as HookInput);
  });
}

export function writeOutput(data: HookOutput): void {
  console.log(JSON.stringify(data));
}
