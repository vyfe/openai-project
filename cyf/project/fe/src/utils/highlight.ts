import hljs from 'highlight.js';

// 为代码块添加语法高亮
export const highlightCode = (html: string): string => {
  // 找到所有的 pre 和 code 标签，并应用语法高亮
  return html.replace(/<pre><code(?:\s+class="([^"]*)")?>([\s\S]*?)<\/code><\/pre>/g, (match, classStr, code) => {
    // 解码 HTML 实体
    code = code
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'");

    let language = '';
    if (classStr) {
      // 提取语言标识符 (如: language-python -> python)
      const langMatch = classStr.match(/language-(\w+)/);
      if (langMatch) {
        language = langMatch[1];
      }
    }

    let highlightedCode = code;
    if (language && hljs.getLanguage(language)) {
      // 如果指定了有效的语言，则使用该语言进行高亮
      highlightedCode = hljs.highlight(code, { language }).value;
    } else {
      // 如果没有指定语言或语言无效，则使用自动检测
      highlightedCode = hljs.highlightAuto(code).value;
    }

    return `<pre><code class="hljs ${classStr || ''}">${highlightedCode}</code></pre>`;
  });
};

// 初始化 highlight.js 样式
export const initHighlight = () => {
  // 可以在这里添加任何初始化代码
  // 目前只需要确保 highlight.js 的样式被加载
};