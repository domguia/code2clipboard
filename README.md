# **Code2Clipboard**

**Effortlessly transform your codebase into AI-ready prompts and insights.**

## 🚀 **What is Code2Clipboard?**

Code2Clipboard is a **developer utility** that scans your codebase, tokenizes content, and generates **LLM-ready prompts** directly to your clipboard. With features like directory tree visualization, token count preview, and whole project prompt generation, it’s designed to save time and supercharge your workflow.

It will will to add to your prompt a full context of your project, so that your prefered AI Assistant can produce the best possible answer.

---

## ✨ **Features**

- 🔍 **Prompt Generator**: Automatically turn your code into structured, tokenized prompts for large language models (LLMs).  
- 🗂️ **Directory Tree Viewer**: Generate token-aware, human-readable directory trees with file sizes and token counts.  
- 📋 **Clipboard-Ready**: Instantly copy file contents, summaries, or prompts to your clipboard for seamless pasting.  
- 📦 **Token Insights**: Analyze token usage across your codebase for any OpenAI-compatible model.  
- ⚙️ **Customizable**: Include/exclude files, set maximum file sizes, and optionally include hidden files.  
- 🖇️ **File Merger**: Merge multiple files into a single clipboard-ready text with contextual headers.  

---

## 📥 **Installation**

### 1. **From PyPI (Recommended)**

```bash
pip install code2clipboard
```

### 2. **From Source**

Clone the repository and install locally:

```bash
git clone https://github.com/domguia/code2clipboard.git
cd code2clipboard
pip install .
```

Or install directly from GitHub:

```bash
pip install git+https://github.com/domguia/code2clipboard.git
```

---

## 🛠️ **Usage**

After installation, the `code2clipboard` CLI is ready to use. By default, it **merges files** and **displays a directory tree**:

```bash
code2clipboard
```

### 🔧 **Options**

- **`--tree`**: Display the directory tree with token counts and file sizes (no merge).
- **`--tokens`**: Only display the total token count (no tree or merge).
- **`--include`**: Include specific file patterns (e.g., `*.py`, `*.md`).
- **`--exclude`**: Exclude specific file patterns (e.g., `*.log`, `node_modules/`).
- **`--add-hidden`**: Include hidden files and directories.
- **`--max-file-size`**: Set a maximum file size (default: 20KB).

### Examples

1. **Generate a directory tree**:
   ```bash
   code2clipboard --tree
   ```

2. **Analyze tokens in Python files only**:
   ```bash
   code2clipboard --tokens --include '*.py'
   ```

3. **Merge files into a clipboard-ready prompt**:
   ```bash
   code2clipboard --include '*.py' '*.md'
   ```

4. **Include hidden files and exclude logs**:
   ```bash
   code2clipboard --add-hidden --exclude '*.log'
   ```

---

## 📋 **Output Examples**

### **Default Behavior (Merge + Tree)**

```bash
code2clipboard
```

**Output:**
```
project/        - 32kb ~6.2k tokens
├── main.py     - 12kb ~3k tokens
├── utils.py    - 8kb ~2k tokens
└── README.md   - 2kb ~512 tokens

(Tree copied to clipboard.)
(All file contents merged and copied to clipboard.)
```

### **Tree Only**

```bash
code2clipboard --tree
```

**Output:**
```
project/        - 32kb ~6.2k tokens
├── main.py     - 12kb ~3k tokens
└── utils.py    - 8kb ~2k tokens

(Tree copied to clipboard.)
```

### **Token Analysis**

```bash
code2clipboard --tokens
```

**Output:**
```
Estimated total tokens: 6.2k
```

---

## 🧑‍💻 **Why Developers Love Code2Clipboard**

- **Speed Up Prompt Creation**: Build prompts directly from your codebase, no manual copy-pasting required.  
- **Token Awareness**: Tailor your prompts to fit within LLM token limits effortlessly.  
- **Clipboard Integration**: Skip the file-by-file workflow—copy everything you need in one go.  
- **Customizable Workflow**: Filter by file types, exclude directories, or focus on specific content.  

---

## 🤝 **Contributing**

We welcome contributions from the community! Here’s how you can get started:

1. Fork this repository.
2. Create a feature branch: `git checkout -b feature-name`.
3. Commit your changes: `git commit -m "Add some feature"`.
4. Push to your branch: `git push origin feature-name`.
5. Open a Pull Request.

---

## 📄 **License**

This project is licensed under the [MIT License](LICENSE).

---

## 🌟 **Feedback & Support**

Found an issue or have a feature request? Open an issue on [GitHub Issues](https://github.com/domguia/code2clipboard/issues). We’d love to hear your feedback!

Happy coding! 🚀

---

### Key Points in This README

1. **Attractive hooks**: The project is framed as an indispensable utility for developers working with AI models.
2. **Installation clarity**: Options for PyPI, GitHub, and local installations make it approachable.
3. **Concise examples**: Highlight real-world use cases for the tool, appealing directly to the pain points of developers.
4. **Encourages contributions**: A clear "Contributing" section invites the open-source community to engage.

Let me know if you need help with any specific section!