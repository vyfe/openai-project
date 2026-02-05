# 代码高亮功能说明

本项目现已支持代码高亮功能，该功能利用 `highlight.js` 库实现。

## 支持的语言

- Python: `language-python`
- JavaScript: `language-javascript` 或 `language-js`
- Java: `language-java`
- C++: `language-cpp`
- HTML: `language-html`
- CSS: `language-css`
- 等等...

## 使用方法

在 Markdown 中使用代码块语法，并指定语言：

```markdown
\```python
def hello_world():
    print("Hello, World!")
\```

\```javascript
function helloWorld() {
    console.log("Hello, World!");
}
\```
```

## 实现细节

- 代码位于 `src/utils/highlight.js`
- 样式定义在 `src/styles/chat-content.css` 中的 `.hljs` 类
- 在 `ChatContent.vue` 中的 `renderMarkdownWithMath` 函数中调用了高亮函数
- 支持暗色主题，确保在不同主题下都有良好的显示效果

## 示例

以下是一个 Python 代码示例：

```python
def fibonacci(n):
    """计算斐波那契数列"""
    if n <= 1:
        return n
    else:
        return fibonacci(n-1) + fibonacci(n-2)

# 输出前10个斐波那契数
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
```

这样，您的聊天应用就能正确显示带语法高亮的代码块了！