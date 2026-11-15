// Number the clickable / typeable things on the page.
// Returns [{n, kind, label}]; every item is tagged with data-hn="<n>".
() => {
  const maxItems = 200;
  const maxLabel = 50;
  const out = [];
  let n = 0;

  document.querySelectorAll("[data-hn]").forEach((el) => el.removeAttribute("data-hn"));

  const labelOf = (el) => {
    const candidates = [
      el.innerText || el.textContent || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("placeholder") || "",
      el.getAttribute("name") || "",
      el.getAttribute("value") || "",
      el.getAttribute("alt") || "",
      el.getAttribute("title") || "",
    ];
    for (const raw of candidates) {
      const text = String(raw).replace(/\s+/g, " ").trim();
      if (text) return text.slice(0, maxLabel);
    }
    return "";
  };

  const kindOf = (el) => {
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute("role") || "").toLowerCase();
    if (role === "button" || role === "link") return role;
    if (tag === "a") return "link";
    if (tag === "input") {
      const type = (el.type || "text").toLowerCase();
      if (type === "submit" || type === "button" || type === "reset") return "button";
      if (type === "checkbox" || type === "radio") return type;
      return "input";
    }
    return tag;
  };

  const isVisible = (el) => {
    if (el.disabled) return false;
    if (el.tagName.toLowerCase() === "input" && el.type === "hidden") return false;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    return true;
  };

  const selector = "a, button, input, select, textarea, [role=button], [role=link]";
  for (const el of document.querySelectorAll(selector)) {
    if (out.length >= maxItems) break;
    if (!isVisible(el)) continue;
    const label = labelOf(el);
    if (!label) continue;
    const kind = kindOf(el);
    n += 1;
    el.setAttribute("data-hn", String(n));
    out.push({ n, kind, label });
  }
  return out;
}
