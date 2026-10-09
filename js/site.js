/* Progressive enhancement: pages and article links work without JavaScript. */
document.documentElement.classList.add("js");
const toggle = document.querySelector(".menu-toggle");
const nav = document.querySelector(".main-nav");
if (toggle && nav) {
  const closeMenu = () => {
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "メニューを開く");
    nav.classList.remove("open");
  };
  toggle.addEventListener("click", () => {
    const opening = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.setAttribute(
      "aria-label",
      opening ? "メニューを閉じる" : "メニューを開く",
    );
    nav.classList.toggle("open", opening);
  });
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      toggle.getAttribute("aria-expanded") === "true"
    ) {
      closeMenu();
      toggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".site-header")) closeMenu();
  });
  nav.addEventListener("focusout", (event) => {
    if (!nav.contains(event.relatedTarget) && event.relatedTarget !== toggle)
      closeMenu();
  });
  matchMedia("(min-width: 761px)").addEventListener("change", closeMenu);
}

const tools = document.querySelector("#blog-tools");
if (tools) {
  const search = document.querySelector("#post-search");
  const buttons = [...tools.querySelectorAll("[data-category]")];
  const cards = [...document.querySelectorAll("#blog-posts .post-card")];
  const params = new URLSearchParams(location.search);
  let category = params.get("category") || "すべて";
  if (!buttons.some((button) => button.dataset.category === category))
    category = "すべて";
  search.value = (params.get("q") || "").slice(0, 200);
  const normalize = (value) =>
    value.normalize("NFKC").toLocaleLowerCase("ja").trim();
  const applyFilters = () => {
    const words = normalize(search.value).split(/\s+/u).filter(Boolean);
    let count = 0;
    for (const card of cards) {
      const matchesCategory =
        category === "すべて" || card.dataset.category === category;
      const content = normalize(card.dataset.search || "");
      const matchesWords = words.every((word) => content.includes(word));
      card.hidden = !(matchesCategory && matchesWords);
      if (!card.hidden) count++;
    }
    for (const button of buttons)
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.category === category),
      );
    document.querySelector("#result-count").textContent = `${count}件の記事`;
    document.querySelector("#empty-state").hidden = count !== 0;
    const url = new URL(location.href);
    if (search.value.trim()) url.searchParams.set("q", search.value.trim());
    else url.searchParams.delete("q");
    if (category !== "すべて") url.searchParams.set("category", category);
    else url.searchParams.delete("category");
    history.replaceState(null, "", url);
  };
  search.addEventListener("input", applyFilters);
  tools.querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });
  for (const button of buttons)
    button.addEventListener("click", () => {
      category = button.dataset.category;
      applyFilters();
    });
  document.querySelector("#clear-filters").addEventListener("click", () => {
    search.value = "";
    category = "すべて";
    applyFilters();
    search.focus();
  });
  tools.hidden = false;
  applyFilters();
  // Preserve existing blog.html#post-id links by moving to the linked card.
  if (location.hash) {
    let id = location.hash.slice(1);
    try {
      id = decodeURIComponent(id);
    } catch {
      /* Invalid escape sequences are literal fragment text. */
    }
    const card = document.getElementById(id);
    if (card) card.scrollIntoView();
  }
}
