import { promises as fs } from "node:fs";
import path from "node:path";
import matter from "gray-matter";

const websiteRoot = process.cwd();
const repoRoot = path.resolve(websiteRoot, "..");
const dataDir = path.join(websiteRoot, "public", "data");
const contentDir = path.join(dataDir, "content");

async function walk(dir) {
  const out = [];
  let entries = [];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full)));
    else out.push(full);
  }
  return out;
}

function relToRepo(absPath) {
  return path.relative(repoRoot, absPath).split(path.sep).join("/");
}

function titleFromFile(file) {
  return path.basename(file, path.extname(file));
}

function normalizeArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function parseExtensions(applyToValue) {
  const source = Array.isArray(applyToValue)
    ? applyToValue.join(",")
    : typeof applyToValue === "string"
      ? applyToValue
      : "";
  const matches = [...source.matchAll(/\*\*\/\*\.([a-zA-Z0-9_-]+)/g)].map((m) => `.${m[1]}`);
  return [...new Set(matches)];
}

async function buildAgents() {
  const root = path.join(repoRoot, "agents");
  const files = (await walk(root)).filter((f) => f.endsWith(".md"));
  const items = [];
  const models = new Set();
  const tools = new Set();

  for (const file of files) {
    const raw = await fs.readFile(file, "utf8");
    const parsed = matter(raw);
    const model = parsed.data.model;
    const toolsList = normalizeArray(parsed.data.tools);
    toolsList.forEach((t) => tools.add(t));
    if (Array.isArray(model)) model.forEach((m) => models.add(String(m)));
    else if (typeof model === "string" && model.trim()) models.add(model.trim());

    const stat = await fs.stat(file);
    items.push({
      title: parsed.data.name || titleFromFile(file),
      description: parsed.data.description || "",
      path: relToRepo(file),
      model: model || undefined,
      tools: toolsList,
      hasHandoffs: Array.isArray(parsed.data.handoffs) && parsed.data.handoffs.length > 0,
      lastUpdated: stat.mtime.toISOString()
    });
  }

  items.sort((a, b) => a.title.localeCompare(b.title));
  return {
    items,
    filters: {
      models: [...models].sort(),
      tools: [...tools].sort()
    }
  };
}

async function buildInstructions() {
  const root = path.join(repoRoot, "instructions");
  const files = (await walk(root)).filter((f) => f.endsWith(".md"));
  const items = [];
  const extensions = new Set();

  for (const file of files) {
    const raw = await fs.readFile(file, "utf8");
    const parsed = matter(raw);
    const applyTo = parsed.data.paths ?? parsed.data.applyTo ?? null;
    const ext = parseExtensions(applyTo);
    ext.forEach((e) => extensions.add(e));
    const stat = await fs.stat(file);
    items.push({
      title: titleFromFile(file),
      description: parsed.data.description || "",
      path: relToRepo(file),
      applyTo,
      extensions: ext,
      lastUpdated: stat.mtime.toISOString()
    });
  }

  items.sort((a, b) => a.title.localeCompare(b.title));
  return {
    items,
    filters: {
      extensions: [...extensions].sort()
    }
  };
}

async function buildSkills() {
  const root = path.join(repoRoot, "skills");
  const files = (await walk(root)).filter((f) => path.basename(f) === "SKILL.md");
  const items = [];
  const categories = new Set();

  for (const skillFile of files) {
    const skillDir = path.dirname(skillFile);
    const dirRel = relToRepo(skillDir);
    const folderName = path.basename(skillDir);
    const parsed = matter(await fs.readFile(skillFile, "utf8"));
    const allFiles = (await walk(skillDir)).map((f) => ({ name: path.relative(skillDir, f).split(path.sep).join("/"), path: relToRepo(f) }));
    const assets = allFiles.filter((f) => f.name !== "SKILL.md");
    const category = dirRel.includes("/") ? dirRel.split("/")[1] : "general";
    categories.add(category);
    const stat = await fs.stat(skillFile);

    items.push({
      id: folderName,
      title: parsed.data.name || folderName,
      description: parsed.data.description || "",
      path: dirRel,
      skillFile: relToRepo(skillFile),
      category,
      hasAssets: assets.length > 0,
      assetCount: assets.length,
      files: allFiles,
      lastUpdated: stat.mtime.toISOString()
    });
  }

  items.sort((a, b) => a.title.localeCompare(b.title));
  return {
    items,
    filters: {
      categories: [...categories].sort()
    }
  };
}

async function buildHooks() {
  const root = path.join(repoRoot, "hooks");
  const readmes = (await walk(root)).filter((f) => path.basename(f).toLowerCase() === "readme.md");
  const items = [];
  const hookEvents = new Set();
  const tags = new Set();

  for (const readmeFile of readmes) {
    const hookDir = path.dirname(readmeFile);
    const id = path.basename(hookDir);
    const parsed = matter(await fs.readFile(readmeFile, "utf8"));

    const hooksJsonPath = path.join(hookDir, "hooks.json");
    let events = [];
    try {
      const hooksJson = JSON.parse(await fs.readFile(hooksJsonPath, "utf8"));
      events = Object.keys(hooksJson.hooks || {});
    } catch {
      events = normalizeArray(parsed.data.hooks);
    }
    events.forEach((h) => hookEvents.add(h));

    const tagList = normalizeArray(parsed.data.tags);
    tagList.forEach((t) => tags.add(t));

    const allFiles = await walk(hookDir);
    const assets = allFiles
      .map((f) => path.relative(hookDir, f).split(path.sep).join("/"))
      .filter((n) => n !== "README.md" && n !== "hooks.json");

    const stat = await fs.stat(readmeFile);
    items.push({
      id,
      title: parsed.data.name || id,
      description: parsed.data.description || "",
      path: relToRepo(hookDir),
      readmeFile: relToRepo(readmeFile),
      hooks: events,
      tags: tagList,
      assets,
      lastUpdated: stat.mtime.toISOString()
    });
  }

  items.sort((a, b) => a.title.localeCompare(b.title));
  return {
    items,
    filters: {
      hooks: [...hookEvents].sort(),
      tags: [...tags].sort()
    }
  };
}

async function buildWorkflows() {
  const root = path.join(repoRoot, "workflows");
  const files = (await walk(root)).filter((f) => f.endsWith(".md"));
  const items = [];
  const triggers = new Set();

  for (const file of files) {
    const parsed = matter(await fs.readFile(file, "utf8"));
    const on = parsed.data.on;
    const triggerList = Array.isArray(on)
      ? on.map(String)
      : on && typeof on === "object"
        ? Object.keys(on)
        : typeof on === "string"
          ? [on]
          : [];
    triggerList.forEach((t) => triggers.add(t));
    const stat = await fs.stat(file);

    items.push({
      title: parsed.data.name || titleFromFile(file),
      description: parsed.data.description || "",
      path: relToRepo(file),
      triggers: triggerList,
      lastUpdated: stat.mtime.toISOString()
    });
  }

  items.sort((a, b) => a.title.localeCompare(b.title));
  return {
    items,
    filters: {
      triggers: [...triggers].sort()
    }
  };
}

async function buildPlugins() {
  const root = path.join(repoRoot, "plugins");
  const pluginJsonFiles = (await walk(root)).filter((f) => f.endsWith(".github/plugin/plugin.json"));
  const items = [];
  const tags = new Set();

  for (const pluginJson of pluginJsonFiles) {
    const parsed = JSON.parse(await fs.readFile(pluginJson, "utf8"));
    const pluginDir = path.dirname(path.dirname(path.dirname(pluginJson)));
    const pluginPath = relToRepo(pluginDir);
    const tagList = normalizeArray(parsed.tags || parsed.keywords);
    tagList.forEach((t) => tags.add(t));

    let itemCount = 0;
    for (const key of ["agents", "commands", "skills", "items"]) {
      if (Array.isArray(parsed[key])) itemCount += parsed[key].length;
    }

    items.push({
      name: parsed.name || path.basename(pluginDir),
      description: parsed.description || "",
      path: pluginPath,
      tags: tagList,
      itemCount,
      external: false,
      repository: null,
      homepage: null,
      author: null,
      source: null
    });
  }

  items.sort((a, b) => a.name.localeCompare(b.name));
  return {
    items,
    filters: {
      tags: [...tags].sort()
    }
  };
}

function buildTools() {
  return {
    items: [],
    filters: {
      categories: [],
      tags: []
    }
  };
}

function buildSamples() {
  return {
    totalRecipes: 0,
    filters: { tags: [] },
    cookbooks: []
  };
}

async function writeJson(name, data) {
  await fs.mkdir(dataDir, { recursive: true });
  await fs.writeFile(path.join(dataDir, name), JSON.stringify(data, null, 2) + "\n", "utf8");
}

async function mirrorRepoTextContent() {
  const resourceRoots = [
    "agents",
    "instructions",
    "skills",
    "hooks",
    "workflows",
    "plugins",
  ];

  await fs.rm(contentDir, { recursive: true, force: true });

  for (const rootName of resourceRoots) {
    const rootPath = path.join(repoRoot, rootName);
    const files = await walk(rootPath);

    for (const file of files) {
      const relativePath = relToRepo(file);
      const destinationPath = path.join(contentDir, relativePath);

      try {
        const content = await fs.readFile(file, "utf8");
        await fs.mkdir(path.dirname(destinationPath), { recursive: true });
        await fs.writeFile(destinationPath, content, "utf8");
      } catch {
        // Skip binary or unreadable files; the website will fall back to GitHub for those.
      }
    }
  }
}

async function main() {
  await writeJson("agents.json", await buildAgents());
  await writeJson("instructions.json", await buildInstructions());
  await writeJson("skills.json", await buildSkills());
  await writeJson("hooks.json", await buildHooks());
  await writeJson("workflows.json", await buildWorkflows());
  await writeJson("plugins.json", await buildPlugins());
  await writeJson("tools.json", buildTools());
  await writeJson("samples.json", buildSamples());
  await mirrorRepoTextContent();
  console.log("Generated website/public/data/*.json");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
