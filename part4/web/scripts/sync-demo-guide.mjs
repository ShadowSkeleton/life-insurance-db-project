// Jingrui Feng (jf4446) - demo guide document generator
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const content = JSON.parse(await readFile(path.join(root, "lib", "demo-guide-content.json"), "utf8"));
const lines = [
  `# ${content.title}`,
  "",
  `${content.intro} The canonical source is \`web/lib/demo-guide-content.json\`.`,
  "",
  ...content.steps.flatMap((step, index) => [`${index + 1}. ${step.title}. ${step.text} This implements ${step.useCase}.`, ""]),
  `Presenter note: ${content.presenterNote}`,
  "",
  "The wellness activity step refreshes the indexed-view count. Activity is evidence for the periodic measurement process. It does not itself create a `RISK_IMPROVEMENT` row or an immediate premium reduction.",
  "",
];
await writeFile(path.join(root, "..", "docs", "demo_guide.md"), lines.join("\n"), "utf8");
