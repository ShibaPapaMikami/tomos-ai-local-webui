const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

function makeElement(tag) {
  return {
    tag,
    children: [],
    className: "",
    dataset: {},
    hidden: false,
    innerHTML: "",
    open: false,
    options: [],
    rows: 0,
    textContent: "",
    value: "",
    append(...items) {
      this.children.push(...items);
      if (tag === "select") this.options.push(...items.filter((item) => item.tag === "option"));
    },
    querySelector(selector) {
      if (selector === "summary") return this.children.find((child) => child.tag === "summary") || null;
      return null;
    },
  };
}

function textTree(node) {
  if (!node) return "";
  return [node.textContent || "", ...(node.children || []).map(textTree)].join("\n");
}

const context = {
  window: {},
  document: {
    createElement: makeElement,
  },
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/training.js", "utf8"), context, { filename: "web/training.js" });

const {
  buildTrainingExamplesFromSessions,
  buildTrainingExamplesFromSet,
  cleanTrainingContent,
  applyCorrectionSaveResult,
  applyCreatedTrainingSet,
  applyDeletedTrainingSet,
  applyTrainingSetSelection,
  createTrainingExport,
  renderTrainingExamples,
  sessionsForTrainingScope,
  shouldSkipTrainingAssistant,
  trainingExportFilenameScope,
} = context.window.GEMMA_TRAINING;

const nowIso = () => "2026-06-17T00:00:00.000Z";
const systemPrompt = "正確に短く答えてください。";
const session = {
  id: "chat-1",
  title: "Gugenkaについて",
  folderId: "folder-1",
  messages: [
    { role: "user", content: "Gugenkaの代表は？" },
    {
      role: "assistant",
      content: "株式会社Gugenkaの代表者は三上昌史氏です。",
      durationSeconds: 4.2,
      runMeta: {
        task: "chat",
        model: "gemma4:12b",
        responseMode: "balanced",
      },
    },
    { role: "user", content: "壊れた回答を保存して" },
    { role: "assistant", content: "エラー: 生成結果を読み取れませんでした" },
    { role: "user", content: "画像つきは教材にしない", images: ["data:image/png;base64,abc"] },
    { role: "assistant", content: "画像の説明です。" },
  ],
};

const examples = buildTrainingExamplesFromSessions({
  sessions: [session],
  scope: "active",
  systemPrompt,
  language: "ja",
  folderNameForSession: () => "テスト",
  nowIso,
});

assert.equal(examples.length, 1);
assert.deepEqual(JSON.parse(JSON.stringify(examples[0].messages)), [
  { role: "system", content: systemPrompt },
  { role: "user", content: "Gugenkaの代表は？" },
  { role: "assistant", content: "株式会社Gugenkaの代表者は三上昌史氏です。" },
]);
assert.equal(examples[0].metadata.folder, "テスト");
assert.equal(examples[0].metadata.session, "Gugenkaについて");
assert.equal(examples[0].metadata.model, "gemma4:12b");
assert.equal(examples[0].metadata.exportedAt, nowIso());

const setExamples = buildTrainingExamplesFromSet({
  set: {
    name: "Gugenka",
    examples: [
      {
        user: "ホロモデルとは？",
        assistant: "ホロモデルはGugenkaのデジタルフィギュアサービスです。",
        task: "chat",
        sourceSessionTitle: "Gugenkaについて",
        createdAt: "2026-06-16T00:00:00.000Z",
      },
      { user: "", assistant: "空の質問は出さない" },
    ],
  },
  systemPrompt,
  nowIso,
});

assert.equal(setExamples.length, 1);
assert.equal(setExamples[0].metadata.scope, "set");
assert.equal(setExamples[0].metadata.trainingSet, "Gugenka");
assert.equal(setExamples[0].messages[2].content, "ホロモデルはGugenkaのデジタルフィギュアサービスです。");

assert.equal(cleanTrainingContent({ content: "  hello  " }), "hello");
assert.equal(cleanTrainingContent({ content: "hello", streaming: true }), "");
assert.equal(cleanTrainingContent({ content: "hello", imagePreviews: ["preview"] }), "");
assert.equal(shouldSkipTrainingAssistant("生成エラー: timed out"), true);
assert.equal(shouldSkipTrainingAssistant("正しい回答です。"), false);

const scopedSessions = [
  { id: "chat-1", folderId: "folder-a" },
  { id: "chat-2", folderId: "folder-b" },
  { id: "chat-3", folderId: "folder-a" },
];
assert.deepEqual(
  JSON.parse(JSON.stringify(sessionsForTrainingScope({
    scope: "all",
    sessions: scopedSessions,
    activeFolderId: "folder-a",
    activeSessionId: "chat-2",
  }))),
  scopedSessions,
);
assert.deepEqual(
  JSON.parse(JSON.stringify(sessionsForTrainingScope({
    scope: "folder",
    sessions: scopedSessions,
    activeFolderId: "folder-a",
    activeSessionId: "chat-2",
  }))),
  [
    { id: "chat-1", folderId: "folder-a" },
    { id: "chat-3", folderId: "folder-a" },
  ],
);
assert.deepEqual(
  JSON.parse(JSON.stringify(sessionsForTrainingScope({
    scope: "active",
    sessions: scopedSessions,
    activeFolderId: "folder-a",
    activeSessionId: "chat-2",
  }))),
  [{ id: "chat-2", folderId: "folder-b" }],
);

const trainingState = { trainingSets: [], activeTrainingSetId: "" };
const createdSet = applyCreatedTrainingSet(trainingState, {
  sets: [{ id: "set-1", name: "Set 1", examples: [] }],
  activeTrainingSetId: "set-1",
});
assert.equal(createdSet.id, "set-1");
assert.equal(trainingState.activeTrainingSetId, "set-1");
assert.equal(applyTrainingSetSelection(trainingState, "set-2"), "set-2");
assert.equal(trainingState.activeTrainingSetId, "set-2");
assert.equal(applyDeletedTrainingSet(trainingState, {
  sets: [{ id: "set-3", name: "Set 3", examples: [] }],
  activeTrainingSetId: "set-3",
  deletedName: "Set 2",
}), "Set 2");
assert.equal(trainingState.activeTrainingSetId, "set-3");
assert.equal(applyCorrectionSaveResult(trainingState, {
  sets: [{ id: "set-4", name: "Set 4", examples: [] }],
  activeTrainingSetId: "set-4",
  set: { id: "set-4", name: "Set 4" },
}).name, "Set 4");
assert.equal(trainingState.activeTrainingSetId, "set-4");

assert.equal(
  trainingExportFilenameScope({
    scope: "folder",
    activeFolder: { name: "テスト フォルダー" },
    slugForFilename: (value, fallback) => value ? value.replace(/\s+/g, "-") : fallback,
  }),
  "テスト-フォルダー",
);

const trainingExport = createTrainingExport({
  scope: "set",
  examples: setExamples,
  activeSet: { name: "Gugenka 修正例" },
  slugForFilename: (value, fallback) => (value ? value.replace(/\s+/g, "-") : fallback),
  timestampForFilename: () => "20260618-010203",
});
assert.equal(trainingExport.count, 1);
assert.equal(trainingExport.filename, "gemma4-training-Gugenka-修正例-20260618-010203.jsonl");
assert.equal(trainingExport.jsonl.endsWith("\n"), true);
assert.equal(JSON.parse(trainingExport.jsonl).metadata.trainingSet, "Gugenka");
assert.equal(
  createTrainingExport({
    scope: "set",
    examples: [],
    slugForFilename: (value, fallback) => fallback,
    timestampForFilename: () => "20260618-010203",
  }),
  null,
);

const trainingList = makeElement("div");
const trainingDetails = makeElement("details");
const trainingSummary = makeElement("summary");
trainingDetails.append(trainingSummary);
renderTrainingExamples({
  list: trainingList,
  details: trainingDetails,
  set: {
    name: "Gugenka",
    examples: [
      {
        id: "example-1",
        user: "ホロモデルとは？",
        assistant: "ホロモデルはGugenkaのデジタルフィギュアサービスです。",
        originalAssistant: "ホロモデルはVTuber向け3Dモデルです。",
        task: "chat",
        sourceSessionTitle: "Gugenkaについて",
        createdAt: "2026-06-16T00:00:00.000Z",
      },
    ],
  },
  t: (key, values = {}) => {
    const labels = {
      "settings.trainingExamplesWithCount": `学習ノートを見る（${values.count}件）`,
      "settings.trainingExamplesEmpty": "空",
      "settings.trainingExampleUser": "元の質問",
      "settings.trainingExampleAssistant": "保存した正しい回答",
      "settings.trainingExampleOriginal": "元のAI回答",
      "settings.trainingExampleNoOriginal": "保存されていません",
      "settings.trainingExampleNote": "メモ",
      "settings.trainingExampleInfo": "情報",
      "settings.trainingExampleSource": "元チャット",
      "settings.trainingExampleTask": "用途",
      "settings.trainingExampleSavedAt": "保存日時",
      "settings.trainingExampleSave": "この回答を保存",
    };
    return labels[key] || key;
  },
});
assert.equal(trainingSummary.textContent, "学習ノートを見る（1件）");
assert.equal(trainingList.children.length, 1);
assert.equal(trainingList.children[0].tag, "details");
assert.equal(trainingList.children[0].children.some((child) => child.tag === "textarea" && child.value.includes("デジタルフィギュア")), true);
const renderedTrainingText = textTree(trainingList);
assert.match(renderedTrainingText, /元の質問/);
assert.match(renderedTrainingText, /元のAI回答/);
assert.match(renderedTrainingText, /Gugenkaについて/);

console.log("training export tests passed");
