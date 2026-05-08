const projectId = "youdao_001";

const $ = (selector) => document.querySelector(selector);

function show(node, payload) {
  node.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw payload.detail || payload;
  }
  return payload;
}

async function loadOverview() {
  const payload = await requestJSON("/api/overview");
  const project = payload.projects?.find((item) => item.project_id === projectId) || payload.projects?.[0];
  if (!project) return;
  $("#qualified").textContent = project.qualified_creator_count ?? 0;
  $("#pool").textContent = project.creator_pool_count ?? 0;
}

async function loadFeishuConfig() {
  const payload = await requestJSON(`/api/projects/feishu/connection?project_id=${projectId}`);
  const config = payload.config;
  if (!config) return;
  $("#feishu_url").value = config.feishu_url || "";
  $("#app_id").value = config.app_id || "";
  show($("#feishu_result"), {
    状态: "已读取本地配置",
    AppSecret: config.app_secret_configured ? "已配置" : "未配置",
    目标: config.target,
  });
}

function currentFeishuPayload() {
  return {
    project_id: projectId,
    feishu_url: $("#feishu_url").value.trim(),
    app_id: $("#app_id").value.trim(),
    app_secret: $("#app_secret").value,
  };
}

$("#save_feishu").addEventListener("click", async () => {
  try {
    const payload = await requestJSON("/api/projects/feishu/connection", {
      method: "POST",
      body: JSON.stringify(currentFeishuPayload()),
    });
    $("#app_secret").value = "";
    show($("#feishu_result"), payload);
  } catch (error) {
    show($("#feishu_result"), error);
  }
});

$("#test_feishu").addEventListener("click", async () => {
  try {
    const payload = await requestJSON("/api/projects/feishu/test", {
      method: "POST",
      body: JSON.stringify(currentFeishuPayload()),
    });
    show($("#feishu_result"), payload);
  } catch (error) {
    show($("#feishu_result"), error);
  }
});

loadOverview().catch(() => undefined);
loadFeishuConfig().catch(() => undefined);
