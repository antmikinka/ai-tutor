"""
Model persistence service for saving and restoring model loading states
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import asyncio

from config.settings import get_settings

logger = logging.getLogger(__name__)

class ModelPersistenceService:
    """
    Service for persisting model loading states across application restarts
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        # Use model_dir as data_dir since data_dir doesn't exist in Settings
        data_dir = getattr(self.settings, 'data_dir', self.settings.model_dir)
        self.persistence_file = data_dir / "model_states.json"
        self.auto_load_file = data_dir / "auto_load_config.json"
        self.model_states = {}
        self.auto_load_config = {"enabled": True, "models": []}

    async def initialize(self):
        """Initialize the persistence service"""
        try:
            logger.info("Initializing Model Persistence Service...")

            # Create data directory if it doesn't exist
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)

            # Load existing states
            await self._load_model_states()
            await self._load_auto_load_config()

            logger.info("Model Persistence Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Model Persistence Service: {e}")
            raise

    async def save_model_state(self, model_name: str, state: Dict[str, Any]):
        """
        Save the state of a loaded model

        Args:
            model_name: Name of the model
            state: Model state information
        """
        try:
            self.model_states[model_name] = {
                "model_name": model_name,
                "saved_at": datetime.utcnow().isoformat(),
                "state": state
            }

            await self._save_model_states()
            logger.debug(f"Saved state for model: {model_name}")

        except Exception as e:
            logger.error(f"Error saving model state for {model_name}: {e}")

    async def get_model_state(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the saved state of a model

        Args:
            model_name: Name of the model

        Returns:
            Model state if found, None otherwise
        """
        try:
            if model_name in self.model_states:
                return self.model_states[model_name]["state"]
            return None

        except Exception as e:
            logger.error(f"Error getting model state for {model_name}: {e}")
            return None

    async def remove_model_state(self, model_name: str):
        """
        Remove the saved state of a model

        Args:
            model_name: Name of the model
        """
        try:
            if model_name in self.model_states:
                del self.model_states[model_name]
                await self._save_model_states()
                logger.debug(f"Removed state for model: {model_name}")

        except Exception as e:
            logger.error(f"Error removing model state for {model_name}: {e}")

    async def get_all_model_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all saved model states

        Returns:
            Dictionary of model states
        """
        return self.model_states.copy()

    async def clear_all_model_states(self):
        """Clear all saved model states"""
        try:
            self.model_states.clear()
            await self._save_model_states()
            logger.info("Cleared all model states")

        except Exception as e:
            logger.error(f"Error clearing model states: {e}")

    async def set_auto_load_config(self, enabled: bool, models: List[str] = None):
        """
        Set auto-load configuration

        Args:
            enabled: Whether auto-load is enabled
            models: List of models to auto-load (optional)
        """
        try:
            self.auto_load_config = {
                "enabled": enabled,
                "models": models or [],
                "updated_at": datetime.utcnow().isoformat()
            }

            await self._save_auto_load_config()
            logger.info(f"Auto-load config updated: enabled={enabled}, models={len(models or [])}")

        except Exception as e:
            logger.error(f"Error setting auto-load config: {e}")

    async def get_auto_load_config(self) -> Dict[str, Any]:
        """
        Get auto-load configuration

        Returns:
            Auto-load configuration
        """
        return self.auto_load_config.copy()

    async def get_models_to_auto_load(self) -> List[str]:
        """
        Get list of models that should be auto-loaded

        Returns:
            List of model names to auto-load
        """
        if not self.auto_load_config.get("enabled", False):
            return []

        return self.auto_load_config.get("models", [])

    async def add_model_to_auto_load(self, model_name: str):
        """
        Add a model to the auto-load list

        Args:
            model_name: Name of the model to add
        """
        try:
            if model_name not in self.auto_load_config["models"]:
                self.auto_load_config["models"].append(model_name)
                self.auto_load_config["updated_at"] = datetime.utcnow().isoformat()
                await self._save_auto_load_config()
                logger.info(f"Added model to auto-load: {model_name}")

        except Exception as e:
            logger.error(f"Error adding model to auto-load: {e}")

    async def remove_model_from_auto_load(self, model_name: str):
        """
        Remove a model from the auto-load list

        Args:
            model_name: Name of the model to remove
        """
        try:
            if model_name in self.auto_load_config["models"]:
                self.auto_load_config["models"].remove(model_name)
                self.auto_load_config["updated_at"] = datetime.utcnow().isoformat()
                await self._save_auto_load_config()
                logger.info(f"Removed model from auto-load: {model_name}")

        except Exception as e:
            logger.error(f"Error removing model from auto-load: {e}")

    async def cleanup_old_states(self, days: int = 7):
        """
        Clean up model states older than specified days

        Args:
            days: Number of days to keep states
        """
        try:
            cutoff_time = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
            models_to_remove = []

            for model_name, state_info in self.model_states.items():
                saved_at = datetime.fromisoformat(state_info["saved_at"]).timestamp()
                if saved_at < cutoff_time:
                    models_to_remove.append(model_name)

            for model_name in models_to_remove:
                del self.model_states[model_name]

            if models_to_remove:
                await self._save_model_states()
                logger.info(f"Cleaned up {len(models_to_remove)} old model states")

        except Exception as e:
            logger.error(f"Error cleaning up old model states: {e}")

    async def _load_model_states(self):
        """Load model states from file"""
        try:
            if self.persistence_file.exists():
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                    self.model_states = data.get("model_states", {})
                logger.debug(f"Loaded {len(self.model_states)} model states")

        except Exception as e:
            logger.error(f"Error loading model states: {e}")
            self.model_states = {}

    async def _save_model_states(self):
        """Save model states to file"""
        try:
            data = {
                "model_states": self.model_states,
                "saved_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }

            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.model_states)} model states")

        except Exception as e:
            logger.error(f"Error saving model states: {e}")

    async def _load_auto_load_config(self):
        """Load auto-load configuration from file"""
        try:
            if self.auto_load_file.exists():
                with open(self.auto_load_file, 'r') as f:
                    self.auto_load_config = json.load(f)
                logger.debug("Loaded auto-load configuration")

        except Exception as e:
            logger.error(f"Error loading auto-load config: {e}")
            self.auto_load_config = {"enabled": True, "models": []}

    async def _save_auto_load_config(self):
        """Save auto-load configuration to file"""
        try:
            with open(self.auto_load_file, 'w') as f:
                json.dump(self.auto_load_config, f, indent=2)

            logger.debug("Saved auto-load configuration")

        except Exception as e:
            logger.error(f"Error saving auto-load config: {e}")

    async def export_configuration(self, export_path: Path):
        """
        Export all model configurations to a file

        Args:
            export_path: Path to export the configuration
        """
        try:
            export_data = {
                "model_states": self.model_states,
                "auto_load_config": self.auto_load_config,
                "exported_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }

            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported configuration to: {export_path}")

        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")

    async def import_configuration(self, import_path: Path):
        """
        Import model configurations from a file

        Args:
            import_path: Path to import the configuration from
        """
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)

            # Validate import data structure
            if "model_states" in import_data:
                self.model_states.update(import_data["model_states"])

            if "auto_load_config" in import_data:
                self.auto_load_config = import_data["auto_load_config"]

            # Save imported data
            await self._save_model_states()
            await self._save_auto_load_config()

            logger.info(f"Imported configuration from: {import_path}")

        except Exception as e:
            logger.error(f"Error importing configuration: {e}")

    def get_persistence_info(self) -> Dict[str, Any]:
        """
        Get information about the persistence service

        Returns:
            Persistence service information
        """
        return {
            "persistence_file": str(self.persistence_file),
            "auto_load_file": str(self.auto_load_file),
            "model_states_count": len(self.model_states),
            "auto_load_enabled": self.auto_load_config.get("enabled", False),
            "auto_load_models_count": len(self.auto_load_config.get("models", [])),
            "files_exist": {
                "persistence": self.persistence_file.exists(),
                "auto_load": self.auto_load_file.exists()
            }
        }