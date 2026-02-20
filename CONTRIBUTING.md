# Contributing to Stock TUI

First off, thank you for considering contributing to Stock TUI! It's people like you that make the open-source community such an amazing place to learn, inspire, and create.

## 🚀 "Issue First" Policy

To keep the project's vision consistent and avoid wasted effort, we require that **every contribution begins with a GitHub Issue.**

- **Bugs**: Open an issue describing the bug, including steps to reproduce and your terminal emulator information.
- **Features/Refactors**: Open an issue to discuss the proposed change. This allows us to agree on the implementation details before you start writing code.

Once the issue is discussed and approved, feel free to submit a Pull Request!

## 🛠️ Getting Started

### 1. Fork and Clone
Fork the repository on GitHub and clone your fork locally:
```bash
git clone https://github.com/your-username/stock-tui.git
cd stock-tui
```

### 2. Environment Setup
Create a virtual environment and install the dependencies:
```bash
python3 -m venv stock_tui/venv
source stock_tui/venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize Security Hooks (Mandatory)
We use `pre-commit` to ensure that no secrets or malformed code enter the repository. You **must** install the hooks before committing:
```bash
pre-commit install
```

## 📝 Commit Style

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This helps us keep a clean, readable history.

**Format**: `<type>(<scope>): <short summary>`

**Common Types**:
- `feat`: A new feature (e.g., `feat(watchlist): add custom sorting`)
- `fix`: A bug fix (e.g., `fix(chart): fix border overlap on resize`)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc.)

## 📬 Submitting a Pull Request

1. **Create a Branch**: Use a descriptive name like `feature/your-feature-name` or `fix/issue-id`.
2. **Verify Locally**: Run the application (`./run.sh`) and verify your changes across at least one compatible high-res terminal (Kitty, Ghostty, or WezTerm).
3. **Commit**: Ensure your local `pre-commit` checks pass.
4. **Push & PR**: Push to your fork and submit a Pull Request to our `main` branch.
5. **Link Issues**: In your PR description, include `Closes #123` to link it to the approved issue.

## ⚖️ License

By contributing to this project, you agree that your contributions will be licensed under its [MIT License](LICENSE).
