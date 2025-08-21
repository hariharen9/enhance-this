# CLI Prompt Enhancer Tool - Development Specification

## Project Overview
Build a fast, reliable CLI tool called `enhance-this` with the command `enhance` that takes a simple prompt as a command-line argument, enhances it using Ollama AI models, displays the enhanced version, and automatically copies it to the clipboard. The tool should be cross-platform and distributed via multiple package managers.

## Core Requirements

### Primary Language: Go (Preferred)
- **Why Go**: Superior performance, single binary distribution, excellent cross-compilation, minimal dependencies
- **Alternative**: Python (if Go expertise is limited)

### Core Functionality
```bash
# Real-world usage examples
enhance "write a blog post about AI"
# Output: "Create a comprehensive blog post about artificial intelligence that educates readers about current AI developments, applications, and implications. Structure the content with: an engaging introduction that hooks the reader, clear explanations of key AI concepts, real-world examples and case studies, discussion of both benefits and challenges, and actionable insights for the target audience. Ensure the tone is accessible to non-technical readers while maintaining accuracy and depth."

enhance "explain quantum computing"
# Output: "Provide a thorough explanation of quantum computing that covers fundamental principles, key concepts, and practical applications. Break down complex topics into digestible sections including: quantum mechanics basics, qubits vs classical bits, quantum algorithms and their advantages, current limitations and challenges, major players and developments in the field, and potential future impact on various industries. Use analogies and examples to make abstract concepts understandable."

enhance "optimize this SQL query"
# Output: "Analyze the provided SQL query and deliver comprehensive optimization recommendations. Examine query execution plan, identify performance bottlenecks, and suggest specific improvements including: index optimization strategies, query restructuring techniques, join optimization, subquery alternatives, proper use of WHERE clauses, and statistics considerations. Provide before/after examples with performance impact estimates and explain the reasoning behind each optimization."

enhance "create a marketing email"
# Output: "Design a high-converting marketing email that drives engagement and achieves specific business objectives. Include strategic elements such as: compelling subject line options with A/B testing suggestions, personalized greeting and segmentation considerations, clear value proposition and benefits, persuasive copy with emotional triggers, strong call-to-action placement and wording, mobile optimization considerations, and follow-up sequence recommendations. Ensure compliance with email marketing best practices and regulations."
```

## Technical Specifications

### 1. Command Line Interface
```
Usage: enhance [OPTIONS] <prompt>

Arguments:
  <prompt>    The initial prompt to enhance

Options:
  -m, --model <MODEL>     Ollama model to use (auto-selects optimal if not specified)
  -t, --temperature <T>   Temperature for generation (0.0-2.0, default: 0.7)
  -l, --length <LENGTH>   Max tokens for enhancement (default: 2000)
  -c, --config <CONFIG>   Configuration file path
  -v, --verbose           Enable verbose output
  -n, --no-copy           Don't copy to clipboard
  -o, --output <FILE>     Save enhanced prompt to file
  -s, --style <STYLE>     Enhancement style (detailed|concise|creative|technical)
  --list-models           List available Ollama models
  --download-model <MODEL> Download specific model from Ollama
  --auto-setup           Automatically setup Ollama with optimal model
  --version               Show version information
  -h, --help              Show help message
```

### 2. Core Features Implementation

#### A. Ollama Integration with Intelligent Model Management
- **Connection**: HTTP API client for Ollama (typically localhost:11434)
- **Automatic Model Selection**: When no model is specified:
  1. Check if Ollama is running (localhost:11434 reachable)
  2. If unreachable: Display "Ollama service unavailable" notification and exit gracefully
  3. If running: List available models via `/api/tags` endpoint
  4. If models available: Auto-select any good available model (prioritizing performance and efficiency)
  5. If no models present: Automatically download and configure a recommended model (e.g., `llama3.1:8b`)
     - Show download progress with progress bar
     - Handle download failures gracefully with retry logic
- **Error Handling**: Check connection timeouts, model availability, download failures
- **Model Management**: Auto-detect available models, validate model names, handle model downloads
- **Streaming**: Support streaming responses for better UX on long prompts and downloads

#### B. Prompt Enhancement Logic
Create sophisticated enhancement templates with real-world examples:

**Example Transformation:**
```
INPUT: "analyze this portfolio deeply and suggest me improvements"

OUTPUT: "Conduct a comprehensive analysis of this portfolio project to identify all potential areas for enhancement. Examine the current implementation thoroughly across design, functionality, content, and user experience aspects. Provide detailed recommendations for improvements that could elevate the portfolio's quality, including but not limited to: additional project showcases, skill demonstrations, interactive elements, performance optimizations, accessibility features, and modern design trends. Ensure your analysis covers both technical and aesthetic considerations to maximize the portfolio's impact on potential employers or clients."
```

**System Prompt Template:**
```
You are an expert prompt engineer specialized in transforming simple requests into comprehensive, actionable prompts that generate superior AI responses.

Transform the user's basic prompt by:
1. EXPANDING SCOPE: Add comprehensive context and multiple dimensions to consider
2. ADDING STRUCTURE: Break down the request into clear, organized components
3. SPECIFYING DELIVERABLES: Define exactly what type of output is expected
4. INCLUDING CONSTRAINTS: Add relevant limitations, requirements, or focus areas
5. ENHANCING CLARITY: Use precise, professional language that eliminates ambiguity
6. ADDING DEPTH: Include multiple layers of analysis or consideration

Enhancement Style: {style}
Original prompt: "{user_prompt}"

Transform this into a detailed, professional prompt that will generate comprehensive, high-quality responses. Make it 3-5x more detailed while maintaining the core intent.
```

**Style-Specific Templates:**

*Detailed Style:*
- Add comprehensive scope with multiple analysis dimensions
- Include specific deliverable requirements
- Add contextual considerations and constraints
- Expand with relevant subcategories and examples

*Concise Style:*
- Focus on clarity and precision without unnecessary verbosity
- Structure the request with clear, actionable components
- Maintain thoroughness while being direct

*Creative Style:*
- Add imaginative elements and unconventional approaches
- Include inspiration for innovative solutions
- Encourage out-of-the-box thinking while maintaining structure

*Technical Style:*
- Add specific technical parameters and methodologies
- Include industry standards and best practices
- Focus on measurable outcomes and technical specifications

#### C. Clipboard Integration
- **Cross-platform clipboard access**:
  - Linux: `xclip` or `xsel`
  - macOS: `pbcopy`
  - Windows: PowerShell or Win32 API
- **Fallback mechanisms** if clipboard unavailable
- **Confirmation feedback** when copied

#### D. Output Display
- **Syntax highlighting** for enhanced prompts
- **Diff view** showing original vs enhanced (optional flag)
- **Progress indicators** during processing
- **Color-coded output** with terminal color support detection

### 3. Configuration System

#### YAML Configuration File (`~/.enhance-this/config.yaml`):
```yaml
# No default_model specified - auto-selects any good available model
default_temperature: 0.7
default_style: "detailed"
ollama_host: "http://localhost:11434"
timeout: 30
max_tokens: 2000
auto_copy: true
display_colors: true
auto_download_model: true  # Automatically download recommended model if none available
enhancement_templates:
  detailed: "path/to/detailed_template.txt"
  concise: "path/to/concise_template.txt"
  creative: "path/to/creative_template.txt"
  technical: "path/to/technical_template.txt"
```

### 4. Performance Optimization
- **Concurrent processing** where possible
- **Connection pooling** for HTTP requests
- **Caching** for frequently used models/templates
- **Minimal startup time** (< 100ms for argument parsing)
- **Memory efficient** streaming for large responses

### 5. Error Handling & Resilience
```
Error Scenarios to Handle:
- Ollama not running/accessible → "Ollama service unavailable - please start Ollama first"
- Network connectivity issues → Retry logic with exponential backoff
- No models available → Auto-download a recommended model with progress indication
- Model download failures → Retry with fallback to different models
- Invalid model names → Suggest available models from list
- Rate limiting → Graceful backoff and retry
- Clipboard access failures → Continue without clipboard, show notification
- Configuration file corruption → Use sensible defaults, warn user
- Insufficient permissions → Clear error messages with solutions
- Model switching during operation → Handle gracefully with status updates
``` corruption
- Insufficient permissions
```

## GitHub Actions Distribution Pipeline

### Required Workflow Files

#### 1. Main Build and Release (`.github/workflows/release.yml`)
```yaml
name: Build and Release
on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            goos: linux
            goarch: amd64
          - os: ubuntu-latest
            goos: linux
            goarch: arm64
          - os: macos-latest
            goos: darwin
            goarch: amd64
          - os: macos-latest
            goos: darwin
            goarch: arm64
          - os: windows-latest
            goos: windows
            goarch: amd64
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Build Binary
        env:
          GOOS: ${{ matrix.goos }}
          GOARCH: ${{ matrix.goarch }}
        run: |
          go build -ldflags="-X main.version=${{ github.ref_name }}" \
                   -o enhance-this-${{ matrix.goos }}-${{ matrix.goarch }}${{ matrix.goos == 'windows' && '.exe' || '' }}
      
      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: enhance-this-${{ matrix.goos }}-${{ matrix.goarch }}
          path: enhance-this-*
  
  release:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: enhance-this-*
          generate_release_notes: true
  
  publish-pypi:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install build dependencies
        run: |
          pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
  
  publish-npm:
    needs: publish-pypi
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - name: Publish NPM wrapper
        run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
  
  update-homebrew:
    needs: publish-pypi
    runs-on: ubuntu-latest
    steps:
      - name: Update Homebrew Formula
        uses: mislav/bump-homebrew-formula-action@v3
        with:
          formula-name: enhance-this
          homebrew-tap: username/homebrew-tap
        env:
          COMMITTER_TOKEN: ${{ secrets.HOMEBREW_TOKEN }}
```

#### 2. Cross-Platform Testing (`.github/workflows/test.yml`)
```yaml
name: Cross-Platform Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11']
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest
      
      - name: Run tests
        run: pytest tests/
      
      - name: Test CLI installation
        run: enhance --version
```

### Required Repository Secrets
Set these in GitHub repository settings:
- `NPM_TOKEN` - NPM authentication token
- `PYPI_TOKEN` - PyPI API token
- `HOMEBREW_TOKEN` - GitHub personal access token for Homebrew tap

### Distribution Strategy with GitHub Actions
1. **Tag-based releases** trigger automated builds
2. **Multi-platform binaries** built in parallel
3. **Package managers updated automatically** after successful binary build
4. **Checksums and signatures** generated for security
5. **Release notes** auto-generated from commits
### 1. Python/Pip Distribution (Primary Distribution Method)

```bash
# Primary installation method
pip install enhance-this

# GitHub Actions automatically builds and publishes to PyPI
```

### 2. NPM Distribution (Node.js Wrapper)
Create a Node.js wrapper that installs the Python package:
```javascript
// package.json - Auto-published via GitHub Actions
{
  "name": "enhance-this",
  "bin": {
    "enhance": "bin/enhance-wrapper.js"
  },
  "scripts": {
    "postinstall": "pip install enhance-this"
  }
}
```

### 3. Homebrew Distribution (Automated Formula Updates)
```python
# setup.py - Python wrapper auto-published via GitHub Actions
import subprocess
import os
from setuptools import setup

# Downloads and installs appropriate binary during pip install
# GitHub Actions handles PyPI publishing automatically on new releases
```

### 4. Homebrew Distribution (Automated Formula Updates)
```ruby
```ruby
# Formula/enhance-this.rb - Auto-updated via GitHub Actions
class EnhanceThis < Formula
  desc "CLI tool to enhance prompts using Ollama AI"
  homepage "https://github.com/username/enhance-this"
  url "https://github.com/username/enhance-this/archive/v1.0.0.tar.gz"
  
  depends_on "go" => :build
  
  def install
    system "go", "build", "-o", bin/"enhance"
  end
end

# GitHub Actions automatically updates Homebrew tap on new releases
```
```

## Additional Enhancement Examples

### Portfolio Analysis Example (Your Use Case)
```
INPUT: "analyze this portfolio deeply and suggest me improvements"

ENHANCED OUTPUT: 
"Conduct a comprehensive analysis of this portfolio project to identify all potential areas for enhancement. Examine the current implementation thoroughly across design, functionality, content, and user experience aspects. Provide detailed recommendations for improvements that could elevate the portfolio's quality, including but not limited to: additional project showcases, skill demonstrations, interactive elements, performance optimizations, accessibility features, and modern design trends. Ensure your analysis covers both technical and aesthetic considerations to maximize the portfolio's impact on potential employers or clients. Structure your feedback with prioritized actionable steps and include specific examples where possible."
```

### Code Review Example
```
INPUT: "review my code"

ENHANCED OUTPUT:
"Perform a thorough code review focusing on multiple quality dimensions: functionality correctness, code organization and architecture, performance implications, security vulnerabilities, maintainability and readability, adherence to best practices and coding standards, error handling robustness, test coverage adequacy, and documentation completeness. Provide specific, actionable feedback with code examples, suggest refactoring opportunities, identify potential bugs or edge cases, and recommend improvements that enhance both immediate functionality and long-term maintainability."
```

### Content Creation Example
```
INPUT: "make this content better"

ENHANCED OUTPUT:
"Enhance this content through comprehensive improvement across multiple dimensions: clarity and readability optimization, audience engagement strategies, structural organization and flow, factual accuracy verification, tone and voice consistency, SEO optimization opportunities, visual content integration suggestions, call-to-action effectiveness, accessibility considerations, and format optimization for the intended platform. Provide specific recommendations with before/after examples, prioritize changes by impact, and ensure the enhanced version maintains the original intent while significantly improving effectiveness."
```

### Phase 1: Core Development (Python)
```python
# Project structure
enhance-this/
├── enhance_this/
│   ├── __init__.py
│   ├── cli.py              # CLI commands using click or argparse
│   ├── ollama_client.py    # Ollama API client
│   ├── enhancer.py         # Prompt enhancement logic
│   ├── clipboard.py        # Cross-platform clipboard
│   └── config.py           # Configuration management
├── templates/              # Enhancement templates
├── scripts/                # Build and distribution scripts
├── tests/                  # Test files
├── setup.py               # Package configuration
├── pyproject.toml         # Modern Python packaging
└── README.md
```

#### 2. Cross-Platform Testing (Python)
- Test on Linux, macOS, Windows
- Verify clipboard functionality across platforms
- Performance benchmarking with different Python versions
- Virtual environment compatibility testing
- Error scenario testing

### Phase 3: Automated Distribution with GitHub Actions
- **GitHub Actions CI/CD pipeline** for automated builds and releases
- **Multi-platform binary compilation** (Linux, macOS, Windows - both amd64 and arm64)
- **Automated NPM publishing** with binary downloader
- **Automated PyPI publishing** with Python wrapper
- **Homebrew formula updates** via automated PR
- **GitHub Releases** with pre-built binaries and checksums
- **Automated testing** across all target platforms
- Documentation and examples deployment

## Key Dependencies (Python)

```python
# Core dependencies
- click>=8.0.0              # CLI framework
- requests>=2.25.0          # HTTP client for Ollama API
- pyyaml>=6.0              # YAML configuration parsing
- pyperclip>=1.8.0         # Cross-platform clipboard
- rich>=10.0.0             # Terminal colors and progress bars
- pathlib                  # Path handling (built-in)
- typing                   # Type hints (built-in)
```

## Testing Strategy
- **Unit tests** for all core functions
- **Integration tests** with Ollama
- **End-to-end tests** for complete workflows
- **Cross-platform testing** via CI/CD
- **Performance benchmarks** for response times

## Documentation Requirements
- **README.md** with installation and usage
- **Man page** for Unix systems
- **Examples** directory with common use cases
- **Configuration guide** for advanced users
- **Troubleshooting guide** for common issues

## Success Metrics
- **Startup time**: < 200ms (Python overhead considered)
- **Enhancement time**: < 5 seconds for typical prompts
- **Package size**: < 5MB installed
- **Memory usage**: < 100MB during operation
- **Cross-platform compatibility**: Linux, macOS, Windows
- **Package manager availability**: pip, npm, brew
- **Python version support**: 3.8+

Build this tool with a focus on developer experience, reliability, and ease of installation. The enhanced prompts should demonstrably improve AI output quality compared to the original simple prompts. Python's rich ecosystem and easy distribution make it ideal for this CLI tool.