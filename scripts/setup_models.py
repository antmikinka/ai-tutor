"""
Model setup and download script for AI Math Tutor
Handles downloading and setting up Qwen3-Omni, Microsoft VibeVoice, and MERaLiON models
"""

import os
import sys
import json
import argparse
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import platform
import hashlib
import shutil

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_dir))

from config.settings import get_settings
from services.model_config import ModelRegistry, get_model_registry
from services.enhanced_model_service import EnhancedModelService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_setup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ModelSetupManager:
    """
    Manager for setting up and downloading AI models
    """

    def __init__(self):
        self.settings = get_settings()
        self.model_registry = get_model_registry()
        self.model_service = EnhancedModelService(self.settings)
        self.setup_config = self._load_setup_config()
        self.downloaded_models = self._load_downloaded_models()

    def _load_setup_config(self) -> Dict[str, Any]:
        """Load model setup configuration"""
        config_path = Path(__file__).parent / "model_config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default model setup configuration"""
        return {
            "download_sources": {
                "huggingface": {
                    "enabled": True,
                    "base_url": "https://huggingface.co",
                    "api_token": os.getenv("HUGGINGFACE_TOKEN")
                },
                "git_lfs": {
                    "enabled": True,
                    "repositories": {
                        "Qwen3-Omni-30B-A3B-Thinking": "Qwen/Qwen3-Omni-30B-A3B-Thinking",
                        "Microsoft-VibeVoice-1.5B": "Microsoft/VibeVoice-1.5B",
                        "MERaLiON-AudioLLM-Whisper-SEA-LION": "MERaLiON/MERaLiON-AudioLLM-Whisper-SEA-LION"
                    }
                }
            },
            "download_options": {
                "max_retries": 3,
                "timeout": 3600,  # 1 hour
                "chunk_size": 1024 * 1024,  # 1MB
                "verify_checksum": True,
                "parallel_downloads": 2
            },
            "system_requirements": {
                "min_memory_gb": {
                    "Qwen3-Omni-30B-A3B-Thinking": 32,
                    "Microsoft-VibeVoice-1.5B": 4,
                    "MERaLiON-AudioLLM-Whisper-SEA-LION": 6
                },
                "gpu_required": {
                    "Qwen3-Omni-30B-A3B-Thinking": True,
                    "Microsoft-VibeVoice-1.5B": False,
                    "MERaLiON-AudioLLM-Whisper-SEA-LION": False
                }
            }
        }

    def _load_downloaded_models(self) -> Dict[str, Any]:
        """Load list of downloaded models"""
        downloaded_file = self.settings.model_dir / "downloaded_models.json"
        if downloaded_file.exists():
            with open(downloaded_file, 'r') as f:
                return json.load(f)
        else:
            return {}

    def _save_downloaded_models(self):
        """Save list of downloaded models"""
        downloaded_file = self.settings.model_dir / "downloaded_models.json"
        with open(downloaded_file, 'w') as f:
            json.dump(self.downloaded_models, f, indent=2)

    async def setup_all_models(self, force_download: bool = False) -> Dict[str, Any]:
        """Setup all required models"""
        logger.info("Starting setup of all models...")

        results = {}
        setup_order = [
            "Qwen3-Omni-30B-A3B-Thinking",
            "Microsoft-VibeVoice-1.5B",
            "MERaLiON-AudioLLM-Whisper-SEA-LION"
        ]

        for model_name in setup_order:
            logger.info(f"Setting up model: {model_name}")
            try:
                result = await self.setup_model(model_name, force_download)
                results[model_name] = result
            except Exception as e:
                logger.error(f"Failed to setup model {model_name}: {e}")
                results[model_name] = {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }

        return results

    async def setup_model(self, model_name: str, force_download: bool = False) -> Dict[str, Any]:
        """Setup a specific model"""
        logger.info(f"Setting up model: {model_name}")

        try:
            # Get model configuration
            model_config = self.model_registry.get_model(model_name)
            if not model_config:
                raise ValueError(f"Model configuration not found: {model_name}")

            # Check system requirements
            if not self._check_system_requirements(model_config):
                raise RuntimeError(f"System requirements not met for {model_name}")

            # Check if model is already downloaded
            model_path = self.settings.get_model_path(model_name)
            if model_path.exists() and not force_download:
                logger.info(f"Model {model_name} already exists at {model_path}")
                return {
                    "success": True,
                    "message": "Model already downloaded",
                    "path": str(model_path),
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Create model directory
            model_path.mkdir(parents=True, exist_ok=True)

            # Download model
            download_result = await self._download_model(model_config, model_path, force_download)

            # Verify download
            if download_result["success"]:
                verification_result = await self._verify_model_download(model_config, model_path)
                if not verification_result["success"]:
                    raise RuntimeError(f"Model verification failed: {verification_result['error']}")

            # Update downloaded models list
            self.downloaded_models[model_name] = {
                "path": str(model_path),
                "downloaded_at": datetime.utcnow().isoformat(),
                "size_gb": download_result.get("size_gb", 0),
                "checksum": download_result.get("checksum"),
                "version": model_config.model_id
            }
            self._save_downloaded_models()

            return {
                "success": True,
                "message": f"Model {model_name} setup successfully",
                "path": str(model_path),
                "size_gb": download_result.get("size_gb", 0),
                "download_time": download_result.get("download_time", 0),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to setup model {model_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _check_system_requirements(self, model_config) -> bool:
        """Check if system meets model requirements"""
        try:
            import psutil

            # Check memory requirements
            available_memory_gb = psutil.virtual_memory().available / (1024**3)
            required_memory = self.setup_config["system_requirements"]["min_memory_gb"].get(
                model_config.name, float('inf')
            )

            if available_memory_gb < required_memory:
                logger.error(f"Insufficient memory for {model_config.name}: need {required_memory}GB, have {available_memory_gb}GB")
                return False

            # Check GPU requirements
            gpu_required = self.setup_config["system_requirements"]["gpu_required"].get(model_config.name, False)
            if gpu_required:
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.error(f"GPU required for {model_config.name} but not available")
                        return False
                except ImportError:
                    logger.error(f"PyTorch not available for GPU check")
                    return False

            # Check disk space
            free_disk_gb = psutil.disk_usage(str(self.settings.model_dir)).free / (1024**3)
            required_disk = model_config.file_size_gb * 2  # Double for safety

            if free_disk_gb < required_disk:
                logger.error(f"Insufficient disk space for {model_config.name}: need {required_disk}GB, have {free_disk_gb}GB")
                return False

            logger.info(f"System requirements check passed for {model_config.name}")
            return True

        except Exception as e:
            logger.error(f"Error checking system requirements: {e}")
            return False

    async def _download_model(self, model_config, model_path: Path, force_download: bool) -> Dict[str, Any]:
        """Download model using appropriate method"""
        logger.info(f"Downloading model {model_config.name} to {model_path}")

        try:
            start_time = datetime.utcnow()

            # Try Git LFS first if enabled
            if self.setup_config["download_sources"]["git_lfs"]["enabled"]:
                if model_config.name in self.setup_config["download_sources"]["git_lfs"]["repositories"]:
                    result = await self._download_with_git_lfs(model_config, model_path, force_download)
                    if result["success"]:
                        return result

            # Fallback to Hugging Face
            if self.setup_config["download_sources"]["huggingface"]["enabled"]:
                result = await self._download_with_huggingface(model_config, model_path, force_download)
                if result["success"]:
                    return result

            raise RuntimeError("No download method available")

        except Exception as e:
            logger.error(f"Error downloading model {model_config.name}: {e}")
            raise

    async def _download_with_git_lfs(self, model_config, model_path: Path, force_download: bool) -> Dict[str, Any]:
        """Download model using Git LFS"""
        logger.info(f"Attempting Git LFS download for {model_config.name}")

        try:
            # Check if Git LFS is installed
            result = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("Git LFS not installed or not in PATH")
                return {"success": False, "error": "Git LFS not available"}

            # Get repository URL
            repo_url = self.setup_config["download_sources"]["git_lfs"]["repositories"].get(model_config.name)
            if not repo_url:
                return {"success": False, "error": "Repository URL not found"}

            # Clone or update repository
            if model_path.exists() and not force_download:
                # Update existing repository
                logger.info(f"Updating existing repository at {model_path}")
                result = subprocess.run(
                    ["git", "-C", str(model_path), "pull"],
                    capture_output=True, text=True, timeout=self.setup_config["download_options"]["timeout"]
                )
            else:
                # Clone new repository
                if model_path.exists():
                    shutil.rmtree(model_path)

                logger.info(f"Cloning repository {repo_url} to {model_path}")
                result = subprocess.run(
                    ["git", "clone", repo_url, str(model_path)],
                    capture_output=True, text=True, timeout=self.setup_config["download_options"]["timeout"]
                )

            if result.returncode != 0:
                logger.error(f"Git LFS download failed: {result.stderr}")
                return {"success": False, "error": result.stderr}

            # Initialize and update Git LFS
            subprocess.run(["git", "-C", str(model_path), "lfs", "install"], check=True)
            subprocess.run(["git", "-C", str(model_path), "lfs", "pull"], check=True)

            # Calculate size
            size_gb = self._calculate_directory_size(model_path) / (1024**3)
            download_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Git LFS download completed successfully for {model_config.name}")

            return {
                "success": True,
                "method": "git_lfs",
                "size_gb": size_gb,
                "download_time": download_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except subprocess.TimeoutExpired:
            logger.error("Git LFS download timed out")
            return {"success": False, "error": "Download timed out"}
        except Exception as e:
            logger.error(f"Error downloading with Git LFS: {e}")
            return {"success": False, "error": str(e)}

    async def _download_with_huggingface(self, model_config, model_path: Path, force_download: bool) -> Dict[str, Any]:
        """Download model using Hugging Face"""
        logger.info(f"Attempting Hugging Face download for {model_config.name}")

        try:
            # Install required packages if not available
            try:
                from huggingface_hub import snapshot_download, HfApi
            except ImportError:
                logger.error("Hugging Face Hub not installed")
                return {"success": False, "error": "Hugging Face Hub not available"}

            # Get API token if available
            api_token = self.setup_config["download_sources"]["huggingface"]["api_token"]

            start_time = datetime.utcnow()

            # Download model
            logger.info(f"Downloading model {model_config.model_id} from Hugging Face")
            downloaded_path = snapshot_download(
                repo_id=model_config.model_id,
                local_dir=str(model_path),
                local_dir_use_symlinks=False,
                cache_dir=str(self.settings.model_cache_dir),
                token=api_token,
                resume_download=True,
                max_workers=self.setup_config["download_options"]["parallel_downloads"]
            )

            # Calculate size
            size_gb = self._calculate_directory_size(model_path) / (1024**3)
            download_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Hugging Face download completed successfully for {model_config.name}")

            return {
                "success": True,
                "method": "huggingface",
                "size_gb": size_gb,
                "download_time": download_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error downloading with Hugging Face: {e}")
            return {"success": False, "error": str(e)}

    async def _verify_model_download(self, model_config, model_path: Path) -> Dict[str, Any]:
        """Verify model download integrity"""
        logger.info(f"Verifying download for {model_config.name}")

        try:
            # Basic verification - check if files exist
            if not model_path.exists():
                return {"success": False, "error": "Model directory does not exist"}

            # Check for essential files based on model type
            essential_files = self._get_essential_files(model_config.type)
            missing_files = []

            for file_pattern in essential_files:
                found = any(file_path.match(file_pattern) for file_path in model_path.rglob("*"))
                if not found:
                    missing_files.append(file_pattern)

            if missing_files:
                return {
                    "success": False,
                    "error": f"Missing essential files: {', '.join(missing_files)}"
                }

            # Calculate checksum if enabled
            checksum = None
            if self.setup_config["download_options"]["verify_checksum"]:
                checksum = self._calculate_checksum(model_path)

            logger.info(f"Model verification passed for {model_config.name}")

            return {
                "success": True,
                "checksum": checksum,
                "verified_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error verifying model download: {e}")
            return {"success": False, "error": str(e)}

    def _get_essential_files(self, model_type) -> List[str]:
        """Get list of essential files for model type"""
        if model_type.value == "reasoning":
            return ["config.json", "pytorch_model.bin", "tokenizer.json"]
        elif model_type.value in ["stt", "fallback_stt"]:
            return ["config.json", "pytorch_model.bin", "processor_config.json"]
        elif model_type.value in ["tts", "fallback_tts"]:
            return ["config.json", "pytorch_model.bin", "processor_config.json"]
        else:
            return ["config.json", "pytorch_model.bin"]

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes"""
        return sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())

    def _calculate_checksum(self, directory: Path) -> str:
        """Calculate checksum for directory"""
        import hashlib

        hash_md5 = hashlib.md5()
        for file_path in sorted(directory.rglob('*')):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def list_downloaded_models(self) -> List[Dict[str, Any]]:
        """List all downloaded models"""
        models = []

        for model_name, info in self.downloaded_models.items():
            model_config = self.model_registry.get_model(model_name)
            if model_config:
                models.append({
                    "name": model_name,
                    "type": model_config.type.value,
                    "path": info["path"],
                    "size_gb": info["size_gb"],
                    "downloaded_at": info["downloaded_at"],
                    "version": info["version"]
                })

        return models

    def get_model_status(self, model_name: str) -> Dict[str, Any]:
        """Get status of a specific model"""
        if model_name in self.downloaded_models:
            info = self.downloaded_models[model_name]
            return {
                "name": model_name,
                "status": "downloaded",
                "path": info["path"],
                "size_gb": info["size_gb"],
                "downloaded_at": info["downloaded_at"]
            }
        else:
            return {
                "name": model_name,
                "status": "not_downloaded",
                "path": None,
                "size_gb": 0,
                "downloaded_at": None
            }

    async def cleanup_old_models(self, keep_latest: int = 2) -> Dict[str, Any]:
        """Clean up old model versions"""
        logger.info("Cleaning up old model versions")

        cleaned_count = 0
        cleaned_size = 0

        try:
            for model_name in list(self.downloaded_models.keys()):
                model_path = Path(self.downloaded_models[model_name]["path"])
                if model_path.exists():
                    size_gb = self._calculate_directory_size(model_path) / (1024**3)
                    shutil.rmtree(model_path)
                    cleaned_size += size_gb
                    cleaned_count += 1

                del self.downloaded_models[model_name]

            self._save_downloaded_models()

            return {
                "success": True,
                "cleaned_count": cleaned_count,
                "cleaned_size_gb": cleaned_size,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error cleaning up old models: {e}")
            return {"success": False, "error": str(e)}

async def main():
    """Main function for model setup"""
    parser = argparse.ArgumentParser(description="Setup AI models for AI Math Tutor")
    parser.add_argument("--model", type=str, help="Specific model to setup (optional)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if model exists")
    parser.add_argument("--list", action="store_true", help="List downloaded models")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old model versions")
    parser.add_argument("--status", type=str, help="Get status of specific model")

    args = parser.parse_args()

    try:
        manager = ModelSetupManager()

        if args.list:
            models = manager.list_downloaded_models()
            print("\nDownloaded Models:")
            for model in models:
                print(f"  - {model['name']} ({model['type']})")
                print(f"    Size: {model['size_gb']:.2f} GB")
                print(f"    Path: {model['path']}")
                print(f"    Downloaded: {model['downloaded_at']}")
                print()

        elif args.status:
            status = manager.get_model_status(args.status)
            print(f"\nModel Status: {status['name']}")
            print(f"  Status: {status['status']}")
            if status['path']:
                print(f"  Path: {status['path']}")
                print(f"  Size: {status['size_gb']:.2f} GB")
                print(f"  Downloaded: {status['downloaded_at']}")
            print()

        elif args.cleanup:
            result = await manager.cleanup_old_models()
            print(f"\nCleanup completed:")
            print(f"  Cleaned {result['cleaned_count']} models")
            print(f"  Freed {result['cleaned_size_gb']:.2f} GB")
            print()

        else:
            # Setup models
            if args.model:
                result = await manager.setup_model(args.model, args.force)
                print(f"\nModel Setup Result:")
                print(f"  Model: {args.model}")
                print(f"  Success: {result['success']}")
                if result['success']:
                    print(f"  Path: {result['path']}")
                    print(f"  Size: {result['size_gb']:.2f} GB")
                    print(f"  Time: {result['download_time']:.2f} seconds")
                else:
                    print(f"  Error: {result.get('error', 'Unknown error')}")
                print()
            else:
                results = await manager.setup_all_models(args.force)
                print("\nModel Setup Results:")
                for model_name, result in results.items():
                    print(f"  {model_name}: {'✓' if result['success'] else '✗'}")
                    if result['success']:
                        print(f"    Path: {result['path']}")
                        print(f"    Size: {result['size_gb']:.2f} GB")
                        print(f"    Time: {result['download_time']:.2f} seconds")
                    else:
                        print(f"    Error: {result.get('error', 'Unknown error')}")
                print()

    except KeyboardInterrupt:
        print("\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        print(f"\nSetup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())