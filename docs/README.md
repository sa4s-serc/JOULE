# HEDGE Documentation

Welcome to the official documentation for HEDGE (Hierarchical Evolutionary Darwin-Green Engine). This technical guide covers the architecture, configuration, and operation of the HEDGE optimization framework.

---

## Technical Guides

### [1. Setup & Configuration](SETUP.md)
Hardware requirements, environment setup, and API key management for LLM integration.

### [2. System Architecture](ARCHITECTURE.md)
A deep dive into the 3-tier domain model, the unified IR system, and the evolutionary optimization pipeline.

### [3. Optimization Layers](MUTATORS.md)
Detailed explanation of the 4-layer hierarchical mutation system: Semantic, Algorithmic, Syntactic, and Micro.

### [4. CLI Reference Manual](CLI.md)
Complete command documentation, option flags, and environment variable references.

---

## Quick Reference

| Goal | Command |
| :--- | :--- |
| **Start Optimization** | `python hedge.py optimize target.py tests.py` |
| **Check Complexity** | `python hedge.py analyze code.py` |
| **View Strategies** | `python hedge.py list-mutators` |
| **Run Benchmarks** | `python hedge.py benchmark --quick` |

---
*Developed by the HEDGE Team*
