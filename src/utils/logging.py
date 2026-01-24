import json
import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ExperimentLogger:
    def __init__(self, base_dir: str = "experiments"):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.experiment_dir = os.path.join(base_dir, self.timestamp)
        os.makedirs(self.experiment_dir, exist_ok=True)

        self.log_file = os.path.join(self.experiment_dir, "evolution.jsonl")
        self.config_file = os.path.join(self.experiment_dir, "config.json")

        logger.info(f"Experiment logging to: {self.experiment_dir}")

    def log_config(self, config: Dict[str, Any]):
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def log_evaluation(
        self,
        generation: int,
        variant_id: str,
        parent_id: str,
        mutation_type: str,
        code: str,
        metrics: Dict[str, Any],
        success: bool,
    ):
        entry = {
            "timestamp": time.time(),
            "generation": generation,
            "variant_id": variant_id,
            "parent_id": parent_id,
            "mutation_type": mutation_type,
            "metrics": metrics,
            "success": success,
            "code_snippet": code[:100] + "..." if len(code) > 100 else code,
            "code_hash": hash(code),
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def save_artifact(self, filename: str, content: str):
        path = os.path.join(self.experiment_dir, filename)
        with open(path, "w") as f:
            f.write(content)
        return path
