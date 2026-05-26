const state = {
  data: null,
  topics: [],
  activeTab: "postIdeas",
  search: "",
  category: "all",
  risk: "all",
  source: "all",
  potential: "all",
};

const fallbackData = {
  generatedAt: new Date().toISOString(),
  dateRange: "Sample data",
  topics: [
    {
      id: "sample-cafe",
      title: "คาเฟ่และเมนูไวรัล",
      sourceType: "trends",
      category: "food",
      contentPotential: "high",
      riskLevel: "low",
      summary: "หัวข้ออาหารและคาเฟ่มักเอาไปทำโพสต์ชวนคุยได้ง่าย เหมาะกับ Creator สาย lifestyle",
      whyItMatters: "เป็นคอนเทนต์ที่คนตอบง่าย แชร์ประสบการณ์ได้ และไม่เสี่ยงเกินไป",
      creatorAngle: "ถามคนในคอมมูนิตี้ว่าช่วงนี้อยากลองเมนูหรือร้านแบบไหน",
      promptIdea: "ช่วงนี้เห็นคนพูดถึงเมนูนี้เต็มฟีด มีใครลองแล้วบ้าง?",
      hashtags: ["#CafeTH", "#FoodTrend", "#รีวิวคาเฟ่"],
      riskNote: "Low risk แต่ควรเลี่ยงการกล่าวอ้างเกินจริงหรือใช้รูปคนอื่นโดยไม่ให้เครดิต",
      sources: [{ title: "Sample topic", url: "https://trends.google.com/trending?geo=TH" }],
      updatedAt: new Date().toISOString(),
    },
  ],
};

const els = {
  content: document.querySelector("#content"),
  template: document.querySelector("#topicCardTemplate"),
  tabs: document.querySelectorAll(".tab"),
  searchInput: document.querySelector("#searchInput"),
  categoryFilter: document.querySelector("#categoryFilter"),
  riskFilter: document.querySelector("#riskFilter"),
  sourceFilter: document.querySelector("#sourceFilter"),
  potentialFilter: document.querySelector("#potentialFilter"),
  lastUpdated: document.querySelector("#lastUpdated"),
  dateRange: document.querySelector("#dateRange"),
  totalTopics: document.querySelector("#totalTopics"),
  postIdeaCount: document.querySelector("#postIdeaCount"),
  riskCount: document.querySelector("#riskCount"),
  hashtagCount: document.querySelector("#hashtagCount"),
};

async function init() {
  bindEvents();
  try {
    const response = await fetch("data/trends.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
  } catch (error) {
    console.warn("Using fallback trend data:", error);
    state.data = fallbackData;
  }
  state.topics = Array.isArray(state.data.topics) ? state.data.topics : [];
  populateCategoryFilter();
  render();
}

function bindEvents() {
  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      state.activeTab = tab.dataset.tab;
      els.tabs.forEach((item) => item.classList.toggle("active", item === tab));
      render();
    });
  });

  els.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    render();
  });

  [
    [els.categoryFilter, "category"],
    [els.riskFilter, "risk"],
    [els.sourceFilter, "source"],
    [els.potentialFilter, "potential"],
  ].forEach(([element, key]) => {
    element.addEventListener("change", (event) => {
      state[key] = event.target.value;
      render();
    });
  });
}

function populateCategoryFilter() {
  const categories = [...new Set(state.topics.map((topic) => topic.category).filter(Boolean))].sort();
  categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = titleCase(category);
    els.categoryFilter.append(option);
  });
}

function filteredTopics() {
  return state.topics.filter((topic) => {
    const haystack = [
      topic.title,
      topic.summary,
      topic.category,
      topic.sourceType,
      topic.riskLevel,
      topic.contentPotential,
      ...(topic.hashtags || []),
    ]
      .join(" ")
      .toLowerCase();

    return (
      (!state.search || haystack.includes(state.search)) &&
      (state.category === "all" || topic.category === state.category) &&
      (state.risk === "all" || topic.riskLevel === state.risk) &&
      (state.source === "all" || topic.sourceType === state.source) &&
      (state.potential === "all" || topic.contentPotential === state.potential)
    );
  });
}

function tabTopics(topics) {
  if (state.activeTab === "postIdeas") {
    return topics.filter((topic) => topic.riskLevel !== "high" && topic.contentPotential !== "low");
  }
  if (state.activeTab === "news") {
    return topics.filter((topic) => topic.sourceType === "news");
  }
  if (state.activeTab === "risk") {
    return topics.filter((topic) => ["medium", "high"].includes(topic.riskLevel));
  }
  return topics;
}

function render() {
  const topics = filteredTopics();
  updateMeta(topics);

  if (state.activeTab === "hashtags") {
    renderHashtags(topics);
    return;
  }

  const visible = tabTopics(topics);
  els.content.innerHTML = "";
  if (!visible.length) {
    els.content.append(emptyState("ไม่มี topic ที่ตรงกับ filter ตอนนี้"));
    return;
  }
  visible.forEach((topic) => els.content.append(renderCard(topic)));
}

function updateMeta(topics) {
  const generated = state.data?.generatedAt ? new Date(state.data.generatedAt) : null;
  els.lastUpdated.textContent = generated ? formatDateTime(generated) : "Unknown";
  els.dateRange.textContent = state.data?.dateRange || "Latest auto feed";
  els.totalTopics.textContent = topics.length;
  els.postIdeaCount.textContent = topics.filter(
    (topic) => topic.riskLevel !== "high" && topic.contentPotential !== "low",
  ).length;
  els.riskCount.textContent = topics.filter((topic) => ["medium", "high"].includes(topic.riskLevel)).length;
  els.hashtagCount.textContent = hashtagCounts(topics).length;
}

function renderCard(topic) {
  const node = els.template.content.firstElementChild.cloneNode(true);
  node.querySelector(".card-kicker").textContent =
    `${titleCase(topic.sourceType || "source")} / ${titleCase(topic.category || "general")} / ${titleCase(topic.contentPotential || "medium")} potential`;
  node.querySelector("h2").textContent = topic.title || "Untitled topic";
  node.querySelector(".summary").textContent = topic.summary || "ไม่มี summary";
  node.querySelector(".why").textContent = topic.whyItMatters || "ทีมสามารถใช้เป็นสัญญาณว่าคนกำลังสนใจเรื่องนี้";
  node.querySelector(".angle").textContent = topic.creatorAngle || "หยิบมุม personal experience หรือชวนคุยแบบไม่ hard news";
  node.querySelector(".prompt").textContent = topic.promptIdea || "ทุกคนคิดยังไงกับเรื่องนี้?";
  node.querySelector(".risk-note").textContent = topic.riskNote || "ตรวจ context ก่อน brief Creator";

  const risk = topic.riskLevel || "medium";
  const riskPill = node.querySelector(".risk-pill");
  riskPill.textContent = `${risk} risk`;
  riskPill.classList.add(`risk-${risk}`);

  const hashtagBox = node.querySelector(".hashtags");
  (topic.hashtags || []).forEach((tag) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = tag;
    hashtagBox.append(chip);
  });

  const sources = node.querySelector(".sources");
  (topic.sources || []).forEach((source, index) => {
    if (!source.url) return;
    const link = document.createElement("a");
    link.className = "source-link";
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.title || `Source ${index + 1}`;
    sources.append(link);
  });

  return node;
}

function renderHashtags(topics) {
  els.content.innerHTML = "";
  const panel = document.createElement("section");
  panel.className = "hashtag-panel";
  const title = document.createElement("h2");
  title.textContent = "Hashtags this week";
  const cloud = document.createElement("div");
  cloud.className = "hashtag-cloud";
  hashtagCounts(topics).forEach(([tag, count]) => {
    const chip = document.createElement("span");
    chip.className = "hashtag-chip";
    chip.innerHTML = `${escapeHtml(tag)} <span>${count} topics</span>`;
    cloud.append(chip);
  });
  panel.append(title, cloud);
  els.content.append(panel);
  if (!cloud.children.length) {
    els.content.append(emptyState("ยังไม่มี hashtag จาก topic ที่เลือก"));
  }
}

function hashtagCounts(topics) {
  const counts = new Map();
  topics.forEach((topic) => {
    (topic.hashtags || []).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function emptyState(message) {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = message;
  return node;
}

function titleCase(value) {
  return String(value || "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDateTime(date) {
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Bangkok",
  }).format(date);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

init();
