# Contributing to enhance-this

We welcome contributions to `enhance-this`! Here are some guidelines to help you get started.

## How to Contribute

1.  **Fork the Repository**: Start by forking the `enhance-this` repository to your GitHub account.

2.  **Clone Your Fork**: Clone your forked repository to your local machine:

    ```bash
    git clone https://github.com/your-username/enhance-this.git
    cd enhance-this
    ```

3.  **Install Dependencies**: Install the project in editable mode with development dependencies:

    ```bash
    pip install -e .[dev]
    ```

4.  **Create a New Branch**: Create a new branch for your feature or bug fix:

    ```bash
    git checkout -b feature/your-feature-name
    ```

5.  **Make Your Changes**: Implement your changes, ensuring you follow the existing code style and conventions.

6.  **Write Tests**: If you add new features or fix bugs, please write corresponding tests to ensure everything works as expected and to prevent regressions.

7.  **Run Tests**: Before submitting your changes, run the test suite to ensure all tests pass:

    ```bash
    pytest tests/
    ```

8.  **Commit Your Changes**: Commit your changes with a clear and concise commit message:

    ```bash
    git commit -m "feat: Add new feature X" # or "fix: Resolve bug Y"
    ```

9.  **Push to Your Fork**: Push your new branch to your forked repository:

    ```bash
    git push origin feature/your-feature-name
    ```

10. **Open a Pull Request**: Go to the original `enhance-this` repository on GitHub and open a new pull request from your forked branch. Provide a detailed description of your changes.

## Code Style

We generally follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code. Please use a linter (like `flake8` or `ruff`) and a formatter (like `black`) to ensure your code adheres to the style guidelines.

## Reporting Bugs

If you find a bug, please open an issue on the [GitHub Issue Tracker](https://github.com/hariharen9/enhance-this/issues). Provide a clear description of the bug, steps to reproduce it, and any relevant error messages.

## Suggesting Features

We welcome feature suggestions! Open an issue on the [GitHub Issue Tracker](https://github.com/hariharen9/enhance-this/issues) to propose new ideas. Describe the feature, why it would be useful, and how it might be implemented.
