# HEDGE Documentation

Welcome to the HEDGE documentation! This directory contains comprehensive guides and references for using the Hierarchical Evolutionary Darwin-Green Engine.

## 📚 Documentation Index

### Getting Started
- **[Quick Start Guide](QUICKSTART.md)** - Get up and running with HEDGE in 5 minutes
- **[Setup Guide](SETUP.md)** - Detailed installation and configuration instructions

### User Guides
- **[Features Overview](FEATURES.md)** - Comprehensive guide to all HEDGE features and capabilities
- **[CLI Reference](CLI.md)** - Complete command-line interface documentation
- **[Configuration Guide](CONFIG.md)** - Configuration management and customization

### Technical Documentation
- **[Architecture Guide](ARCHITECTURE.md)** - System design and IR structure
- **[Mutators Guide](MUTATORS.md)** - Mutation strategies and extending mutators
- **[API Reference](API.md)** - Python API documentation

### Development
- **[Contributing Guide](CONTRIBUTING.md)** - Development guidelines and standards
- **[Testing Guide](TESTING.md)** - Running tests and adding new test cases

## 🚀 Quick Navigation

### New to HEDGE?
1. Start with the **[Quick Start Guide](QUICKSTART.md)**
2. Try the examples: `python hedge.py optimize examples/target_fib.py examples/test_target_fib.py`
3. Read the **[Features Overview](FEATURES.md)** to understand capabilities

### Looking for Specific Information?
- **Commands and Options**: [CLI Reference](CLI.md)
- **Configuration Options**: [Configuration Guide](CONFIG.md)
- **System Architecture**: [Architecture Guide](ARCHITECTURE.md)
- **Extending HEDGE**: [Mutators Guide](MUTATORS.md)

## 🎯 Common Use Cases

### Basic Code Optimization
```bash
# Quick optimization
hedge optimize mycode.py test_mycode.py

# With visualization
hedge optimize mycode.py test_mycode.py --visualize
```
📖 **See**: [Quick Start Guide](QUICKSTART.md), [CLI Reference](CLI.md)

### Advanced AI-Powered Optimization
```bash
# Semantic-level optimization with LLM
hedge optimize mycode.py test_mycode.py --level advanced
```
📖 **See**: [Features Overview](FEATURES.md), [Setup Guide](SETUP.md)

### Code Analysis and Metrics
```bash
# Analyze code complexity
hedge analyze mycode.py --detailed
```
📖 **See**: [CLI Reference](CLI.md), [Features Overview](FEATURES.md)

### Project Management
```bash
# Create organized optimization project
hedge project init my_optimization_project
```
📖 **See**: [Quick Start Guide](QUICKSTART.md), [CLI Reference](CLI.md)

### Performance Benchmarking
```bash
# Test HEDGE on example problems
hedge benchmark --quick
```
📖 **See**: [CLI Reference](CLI.md), [Features Overview](FEATURES.md)

## 🔧 Configuration and Customization

### Configuration Management
```bash
# Interactive setup
hedge config init

# View current settings
hedge config show

# Set specific options
hedge config set optimization.default_level advanced
```
📖 **See**: [Configuration Guide](CONFIG.md), [Setup Guide](SETUP.md)

### Custom Optimization Layers
```bash
# Use specific optimization layers
hedge optimize mycode.py test_mycode.py --layers algorithmic,micro
```
📖 **See**: [Features Overview](FEATURES.md), [Mutators Guide](MUTATORS.md)

## 🏗️ Architecture and Internals

### Understanding HEDGE's Design
- **IR-Only Mutations**: All transformations on typed intermediate representation
- **Hierarchical Layers**: Semantic → Algorithmic → Syntactic → Micro
- **Multi-Objective Optimization**: Pareto front balancing energy vs execution time

📖 **See**: [Architecture Guide](ARCHITECTURE.md), [Features Overview](FEATURES.md)

### Extending HEDGE
- **Custom Mutators**: Add new optimization strategies
- **Custom Metrics**: Define domain-specific optimization objectives
- **Plugin System**: Integrate third-party optimizations

📖 **See**: [Mutators Guide](MUTATORS.md), [Contributing Guide](CONTRIBUTING.md)

## 🧪 Testing and Development

### Running Tests
```bash
# Run test suite
make test

# Run with coverage
make test-coverage

# Run examples
make examples
```
📖 **See**: [Testing Guide](TESTING.md), [Contributing Guide](CONTRIBUTING.md)

### Development Setup
```bash
# Setup development environment
make setup
make dev-install

# Code quality checks
make lint
make format
```
📖 **See**: [Contributing Guide](CONTRIBUTING.md)

## 📊 Examples and Tutorials

### Built-in Examples
- **Fibonacci Optimization**: O(2^n) → O(n) transformation
- **Search Optimization**: Linear search improvements
- **Complex Algorithms**: Multi-layered optimizations

```bash
# Run all examples
python scripts/run_examples.py

# Individual examples
hedge optimize examples/target_fib.py examples/test_target_fib.py
```

### Tutorial Notebooks
- **Research Template**: Jupyter notebooks for analysis
- **Benchmark Analysis**: Performance comparison studies
- **Custom Mutator Development**: Extending HEDGE

📖 **See**: Project templates via `hedge project init --template research`

## 🆘 Troubleshooting

### Common Issues
- **Installation Problems**: [Setup Guide](SETUP.md)
- **Configuration Issues**: [Configuration Guide](CONFIG.md)
- **API Key Setup**: [Setup Guide](SETUP.md)
- **Performance Issues**: [Features Overview](FEATURES.md)

### Getting Help
```bash
# Command help
hedge --help
hedge optimize --help

# Configuration validation
hedge config validate

# System information
hedge config show
```

### Support Resources
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Community support and questions
- **Documentation**: Comprehensive guides and references

## 🔄 Version History

### v1.0.0 (Current)
- **Modern CLI Interface**: Rich console output and organized commands
- **Project Management**: Template-based project creation and management
- **Enhanced Analysis**: Detailed code analysis with recommendations
- **Configuration System**: YAML-based configuration with multiple sources
- **Benchmarking Suite**: Built-in performance testing

### Previous Versions
- **v0.x**: Development versions with experimental features

📖 **See**: [Migration Guide](MIGRATION.md) for upgrade information

## 🤝 Contributing

We welcome contributions to HEDGE! Whether you're fixing bugs, adding features, improving documentation, or sharing examples, your contributions help make HEDGE better for everyone.

### Ways to Contribute
- **Bug Reports**: Report issues and problems
- **Feature Requests**: Suggest new capabilities
- **Code Contributions**: Fix bugs and add features
- **Documentation**: Improve guides and examples
- **Testing**: Add test cases and improve coverage

📖 **See**: [Contributing Guide](CONTRIBUTING.md)

## 📄 License

HEDGE is released under the MIT License. See the [LICENSE](../LICENSE) file for details.

---

**Happy Optimizing with HEDGE!** 🚀

For questions, issues, or contributions, please visit our [GitHub repository](https://github.com/your-org/hedge).
