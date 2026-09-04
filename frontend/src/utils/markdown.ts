function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineFormat(text: string): string {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderBlock(block: string): string {
  if (/^###\s+/.test(block)) {
    return `<h3>${inlineFormat(block.replace(/^###\s+/, ""))}</h3>`;
  }
  if (/^##\s+/.test(block)) {
    return `<h2>${inlineFormat(block.replace(/^##\s+/, ""))}</h2>`;
  }
  if (/^#\s+/.test(block)) {
    return `<h1>${inlineFormat(block.replace(/^#\s+/, ""))}</h1>`;
  }
  if (/^>\s?/m.test(block) && block.split("\n").every((line) => line.startsWith(">") || line.trim() === "")) {
    const quote = block
      .split("\n")
      .map((line) => line.replace(/^>\s?/, ""))
      .join("\n");
    return `<blockquote>${inlineFormat(quote).replace(/\n/g, "<br />")}</blockquote>`;
  }
  if (/^[-*]\s+/m.test(block) && block.split("\n").every((line) => /^[-*]\s+/.test(line) || line.trim() === "")) {
    const items = block
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => `<li>${inlineFormat(line.replace(/^[-*]\s+/, ""))}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }
  if (/^\d+\.\s+/m.test(block) && block.split("\n").every((line) => /^\d+\.\s+/.test(line) || line.trim() === "")) {
    const items = block
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => `<li>${inlineFormat(line.replace(/^\d+\.\s+/, ""))}</li>`)
      .join("");
    return `<ol>${items}</ol>`;
  }
  return `<p>${inlineFormat(block).replace(/\n/g, "<br />")}</p>`;
}

export function renderMarkdown(source: string): string {
  const fences: string[] = [];
  const withFences = source.replace(/```[\w-]*\n([\s\S]*?)```/g, (_match, code: string) => {
    const token = `@@FENCE${fences.length}@@`;
    fences.push(`<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`);
    return `\n\n${token}\n\n`;
  });

  const html = withFences
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const fence = block.match(/^@@FENCE(\d+)@@$/);
      if (fence) {
        return fences[Number(fence[1])];
      }
      return renderBlock(block);
    })
    .join("");

  return html;
}
